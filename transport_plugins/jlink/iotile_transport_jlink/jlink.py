"""A DeviceAdapter that uses an attached jlink device for transport."""

# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import logging
import pylink
from typedargs.exceptions import ArgumentError
from iotile.core.exceptions import HardwareError
from iotile.core.hw.exceptions import DeviceAdapterError
from iotile.core.hw.transport.adapter import StandardDeviceAdapter
from iotile.core.hw.reports import IOTileReportParser
from iotile.core.utilities import SharedLoop
from .devices import KNOWN_DEVICES, DEVICE_ALIASES
from .multiplexers import KNOWN_MULTIPLEX_FUNCS
from .jlink_background import AsyncJLink


# pylint:disable=invalid-name;This is not a constant so its name is okay
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class JLinkAdapter(StandardDeviceAdapter):
    """Wrapper around JLink based transport layer.

    Args:
        port (str): The port string that we were created with.  This should have the
            following format if it is not None or "":
            [device=<device_name>;<other_arg>=<other_value>][<optional config file name>]
    """

    ExpirationTime = 600000
    POLLING_INTERFACES = ["rpc", "tracing", "streaming"]

    def __init__(self, port, name=__name__, loop=SharedLoop, **kwargs):
        super(JLinkAdapter, self).__init__(name, loop)
        self._default_device_info = None
        self._device_info = None
        self._control_info = None
        self._jlink_serial = None
        self._mux_func = None
        self._channel = None
        self._jlink_async = AsyncJLink(self, loop)
        self._task = loop.add_task(None, name="JLINK Adapter stopper", finalizer=self.stop)
        self._connection_id = None
        self.jlink = None
        self.connected = False
        self.opened_interfaces = {
            "rpc": False,
            "tracing": False,
            "streaming": False,
            "debug": False,
            "script": False
            }
        self.report_parser = IOTileReportParser(
            report_callback=self._on_report, error_callback=self._on_report_error)

        self.set_config('probe_required', True)
        self.set_config('probe_supported', True)

        self._parse_port(port)

    def _parse_port(self, port):
        if port is None or len(port) == 0:
            return

        if '@' in port:
            raise ArgumentError("Configuration files are not yet supported as part of a port argument", port=port)

        pairs = port.split(';')
        for pair in pairs:
            name, _, value = pair.partition('=')
            if len(name) == 0 or len(value) == 0:
                continue

            name = name.strip()
            value = value.strip()

            if name == 'device':
                device_name = value
                if device_name in DEVICE_ALIASES:
                    device_name = DEVICE_ALIASES[device_name]
                if device_name in KNOWN_DEVICES:
                    self._default_device_info = KNOWN_DEVICES.get(device_name)
                else:
                    raise ArgumentError("Unknown device name or alias, please select from known_devices", device_name=device_name, known_devices=[x for x in DEVICE_ALIASES.keys()])
            elif name == 'serial':
                self._jlink_serial = value
            elif name == 'mux':
                mux = value
                if mux in KNOWN_MULTIPLEX_FUNCS:
                    self._mux_func = KNOWN_MULTIPLEX_FUNCS[mux]
                else:
                    raise ArgumentError("Unknown multiplexer, please select from known_multiplex_funcs", mux=mux, known_multiplex_funcs=[x for x in KNOWN_MULTIPLEX_FUNCS.keys()])

    def _parse_conn_string(self, conn_string):
        """Parse a connection string passed from 'debug -c' or 'connect_direct'
            Returns True if any settings changed in the debug port, which
            would require a jlink disconnection """
        disconnection_required = False

        """If device not in conn_string, set to default info"""
        if conn_string is None or 'device' not in conn_string:
            if self._default_device_info is not None and self._device_info != self._default_device_info:
                disconnection_required = True
                self._device_info = self._default_device_info

        if conn_string is None or len(conn_string) == 0:
            return disconnection_required

        if '@' in conn_string:
            raise ArgumentError("Configuration files are not yet supported as part of a connection string argument",
                                conn_string=conn_string)

        pairs = conn_string.split(';')
        for pair in pairs:
            name, _, value = pair.partition('=')
            if len(name) == 0 or len(value) == 0:
                continue

            name = name.strip()
            value = value.strip()

            if name == 'device':
                if value in DEVICE_ALIASES:
                    device_name = DEVICE_ALIASES[value]
                if device_name in KNOWN_DEVICES:
                    device_info = KNOWN_DEVICES.get(device_name)
                    if self._device_info != device_info:
                        self._device_info = device_info
                        disconnection_required = True
                else:
                    raise ArgumentError("Unknown device name or alias, please select from known_devices",
                                        device_name=value, known_devices=[x for x in DEVICE_ALIASES.keys()])
            elif name == 'channel':
                if self._mux_func is not None:
                    if self._channel != int(value):
                        self._channel = int(value)
                        disconnection_required = True
                else:
                    print("Warning: multiplexing architecture not selected, channel will not be set")
        return disconnection_required

    def _on_report(self, report, context):
        conn_string = self._get_property(self._connection_id, 'connection_string')
        self.notify_event(conn_string, 'report', report)

        return False

    def _on_report_error(self, code, message, context):
        print("Report Error, code=%d, message=%s" % (code, message))
        self._logger.critical("Error receiving reports, no more reports will be processed on this adapter, code=%d, msg=%s", code, message)

    def add_trace(self, trace):
        conn_string = self._get_property(self._connection_id, 'connection_string')
        self.notify_event(conn_string, 'trace', trace)

    async def _try_connect(self, connection_string):
        """If the connecton string settings are different, try and connect to an attached device"""
        if self._parse_conn_string(connection_string):
            if self.connected is True:
                info = {
                    "reason": "Reconnection",
                    "expected": True
                }
                self.notify_event(connection_string, 'disconnection', info)
                self.connected = False
                await self.stop()

            if self._mux_func is not None:
                self._mux_func(self._channel)

            if self._device_info is None:
                raise ArgumentError("Missing device name or alias, specify using device=name in port string "
                                    "or -c device=name in connect_direct or debug command",
                                    known_devices=[x for x in DEVICE_ALIASES.keys()])

            try:
                await self._jlink_async.connect_jlink(
                    self._jlink_serial, self._device_info.jlink_name)
                self.connected = True
            except pylink.errors.JLinkException as exc:
                if exc.code == exc.VCC_FAILURE:
                    raise HardwareError("No target power detected", code=exc.code,
                                        suggestion="Check jlink connection and power wiring")

                raise
            except:
                raise

    async def stop(self, _task=None):
        """Asynchronously stop this adapter and release all resources."""

        logger.info("Stopping JLINK adapter")
        if self.connected == True:
            await self.disconnect(self._connection_id)

        if self._task.stopped:
            return

        await self._jlink_async.close_jlink()

    async def _find_device_behind_jlink(self):
        control_info = None
        device_name = None

        for device_name in DEVICE_ALIASES.keys():
            try:
                dev = DEVICE_ALIASES[device_name]
                await self._jlink_async.connect_jlink(self._jlink_serial, dev)

                device_info = KNOWN_DEVICES.get(dev)
                control_info = await self._jlink_async.find_control_structure(
                    device_info.ram_start, device_info.ram_size)

                await self._jlink_async.close_jlink()
                break # only one device can be connected at a time and it was found
            except pylink.errors.JLinkException as e:
                logger.debug("Jlink probe failed to connect to {}".format(dev))
                continue

        return control_info, device_name

    async def _find_connected_device(self, device_info, control_info):
        device_name = None

        if device_info:
            try:
                control_info = await self._jlink_async.verify_control_structure(
                    device_info, control_info)

                for alias, device in DEVICE_ALIASES.items():
                    if device == device_info.jlink_name:
                        device_name = alias
                        break
            except HardwareError as e:
                logger.warning("Event though jlink is connected, control structure is not found", exc_info=True)

        return control_info, device_name

    async def probe(self):
        """Send advertisements for all connected devices."""
        if self.connected:
            control_info, device_name = await self._find_connected_device(
                self._device_info, self._control_info)
        else:
            control_info, device_name = await self._find_device_behind_jlink()

        if not control_info or not device_name:
            return

        info = {
            'connection_string': "device={}".format(device_name),
            'uuid': control_info.uuid,
            'signal_strength': 100
        }

        conn_string = None
        if self._connection_id:
            conn_string = self._get_property(self._connection_id, 'connection_string')
        self.notify_event(conn_string, 'device_seen', info)

    async def debug(self, conn_id, name, cmd_args):
        """Asynchronously complete a named debug command.

        The command name and arguments are passed to the underlying device adapter
        and interpreted there.  If the command is long running, progress_callback
        may be used to provide status updates.

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            name (string): the name of the debug command we want to invoke
            cmd_args (dict): any arguments that we want to send with this command.
        """
        known_commands = {
            'read_memory': self._jlink_async.debug_read_memory,
            'write_memory': self._jlink_async.debug_write_memory,
            'program_flash': self._jlink_async.program_flash
        }

        self._ensure_connection(conn_id, True)

        func = known_commands.get(name)
        if name is None:
            raise ArgumentError("Unsupported command: %s" % name)

        return await func(self._device_info, self._control_info, cmd_args)


    async def connect(self, conn_id, connection_string):
        """Connect to a device by its connection_string

        This function asynchronously connects to a device by device type.
        See iotile_transport_jlink_devices.py
        """
        await self._try_connect(connection_string)
        self._setup_connection(conn_id, connection_string)

        try:
            self._control_info = await self._jlink_async.verify_control_structure(
                self._device_info, self._control_info)

            await self._jlink_async.change_state_flag(
                self._control_info, AsyncJLink.CONNECTION_BIT, True)
        except HardwareError as e:
            logger.warning("RPC, streaming and tracing won't work, but device still can be flashed or debugged",
                exc_info=True)

        self._connection_id = conn_id

    async def disconnect(self, conn_id):
        self._teardown_connection(conn_id)

        if not self._control_info: # direct debug connection case
            return

        try:
            if self.opened_interfaces["streaming"]:
                await self.close_interface(conn_id, "streaming")
            if self.opened_interfaces["tracing"]:
                await self.close_interface(conn_id, "tracing")
            if self.opened_interfaces["rpc"]:
                await self.close_interface(conn_id, "rpc")

            await self._jlink_async.change_state_flag(
                self._control_info, AsyncJLink.CONNECTION_BIT, False)
            self.connected = False
        except pylink.errors.JLinkReadException:
            logger.warning("Error disconnecting jlink adapter", exc_info=True)

    async def open_interface(self, conn_id, interface):
        self._ensure_connection(conn_id, True)

        if self.opened_interfaces[interface]:
            return

        self.opened_interfaces[interface] = True

        if (interface == "tracing" or interface == "streaming") and self._control_info.version < 2:
            raise DeviceAdapterError(conn_id, 'open_interface',
                'Controller firmware does not support streaming or tracing interfaces')

        if interface == "tracing":
            await self._jlink_async.change_state_flag(
                self._control_info, AsyncJLink.TRACE_BIT, True)
        elif interface == "streaming":
            await self._jlink_async.change_state_flag(
                self._control_info, AsyncJLink.STREAM_BIT, True)
            await self._jlink_async.notify_sensor_graph(
                self._device_info, self._control_info, True)

        if interface in JLinkAdapter.POLLING_INTERFACES:
            await self._jlink_async.start_polling(self._control_info)

    async def close_interface(self, conn_id, interface):
        self._ensure_connection(conn_id, False)

        if not self.opened_interfaces[interface]:
            return

        self.opened_interfaces[interface] = False

        if interface == "tracing":
            await self._jlink_async.change_state_flag(
                self._control_info, AsyncJLink.TRACE_BIT, False)
        elif interface == "streaming":
            await self._jlink_async.change_state_flag(
                self._control_info, AsyncJLink.STREAM_BIT, False)
            try:
                await self._jlink_async.notify_sensor_graph(
                    self._device_info, self._control_info, False)
            except DeviceAdapterError:
                logger.debug("Exception sending rpc to notify SG", exc_info=True)

        if interface in JLinkAdapter.POLLING_INTERFACES:
            await self._jlink_async.stop_polling()

    async def send_rpc(self, conn_id, address, rpc_id, payload, timeout, retries=5):

        """Asynchronously send an RPC to this IOTile device.

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            address (int): the addres of the tile that we wish to send the RPC to
            rpc_id (int): the 16-bit id of the RPC we want to call
            payload (bytearray): the payload of the command
            timeout (float): the number of seconds to wait for the RPC to execute
        """

        # Default to polling for the response every 1 millisecond
        # FIXME, add an exponential polling backoff so that we wait 1, 2, 4, 8, etc ms
        self._ensure_connection(conn_id, True)

        response = None

        for attempt in range(retries):
            try:
                response = await self._jlink_async.send_rpc(
                    self._device_info, self._control_info,
                    address, rpc_id, payload, timeout)
            except HardwareError as exc:
                if exc.params.get('external_gate_error') == 1:
                    logger.debug("Unsuccessful RPC, attempt %d of %d", attempt, retries)
                else:
                    raise
            except:
                raise

            if response is not None:
                return response['payload']

        raise DeviceAdapterError(conn_id, 'send_rpc', 'Unable to get ExternalGate')

    async def send_script(self, conn_id, data):
        """Asynchronously send a a script to this IOTile device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            data (string): the script to send to the device
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)
        """
        self._ensure_connection(conn_id, True)

        await self._jlink_async.send_script(self._device_info, self._control_info, data)
