"""A DeviceAdapter that uses an attached jlink device for transport."""

# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import logging
import pylink
from typedargs.exceptions import ArgumentError
from iotile.core.exceptions import HardwareError
from iotile.core.hw.transport.adapter import DeviceAdapter
from .devices import KNOWN_DEVICES, DEVICE_ALIASES
from .multiplexers import KNOWN_MULTIPLEX_FUNCS
from .jlink_background import JLinkControlThread


# pylint:disable=invalid-name;This is not a constant so its name is okay
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class JLinkAdapter(DeviceAdapter):
    """Wrapper around JLink based transport layer.

    Args:
        port (str): The port string that we were created with.  This should have the
            following format if it is not None or "":
            [device=<device_name>;<other_arg>=<other_value>][<optional config file name>]
    """

    ExpirationTime = 600000

    def __init__(self, port, on_scan=None, on_disconnect=None, **kwargs):
        super(JLinkAdapter, self).__init__()
        self._default_device_info = None
        self._device_info = None
        self._control_info = None
        self._jlink_serial = None
        self._mux_func = None
        self._channel = None
        self._control_thread = None
        self._connection_id = None
        self.jlink = None

        self._parse_port(port)

        if on_scan is not None:
            self.add_callback('on_scan', on_scan)

        if on_disconnect is not None:
            self.add_callback('on_disconnect', on_disconnect)

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

    def _try_connect(self, connection_string):
        """If the connecton string settings are different, try and connect to an attached device"""
        if self._parse_conn_string(connection_string):
            self._trigger_callback('on_disconnect', self.id, self._connection_id)

            self.stop_sync()

            if self._mux_func is not None:
                self._mux_func(self._channel)

            if self._device_info is None:
                raise ArgumentError("Missing device name or alias, specify using device=name in port string "
                                    "or -c device=name in connect_direct or debug command",
                                    known_devices=[x for x in DEVICE_ALIASES.keys()])

            try:
                self.jlink = pylink.JLink()
                self.jlink.open(serial_no=self._jlink_serial)
                self.jlink.set_tif(pylink.enums.JLinkInterfaces.SWD)
                self.jlink.connect(self._device_info.jlink_name)
                self.jlink.set_little_endian()
            except pylink.errors.JLinkException as exc:
                if exc.code == exc.VCC_FAILURE:
                    raise HardwareError("No target power detected", code=exc.code,
                                        suggestion="Check jlink connection and power wiring")

                raise
            except:
                raise

            self._control_thread = JLinkControlThread(self.jlink)
            self._control_thread.start()

            self.set_config('probe_required', True)
            self.set_config('probe_supported', True)

    def stop_sync(self):
        """Synchronously stop this adapter and release all resources."""

        if self._control_thread is not None and self._control_thread.is_alive():
            self._control_thread.stop()
            self._control_thread.join()

        if self.jlink is not None:
            self.jlink.close()

    def probe_async(self, callback):
        """Send advertisements for all connected devices.

        Args:
            callback (callable): A callback for when the probe operation has completed.
                callback should have signature callback(adapter_id, success, failure_reason) where:
                    success: bool
                    failure_reason: None if success is True, otherwise a reason for why we could not probe
        """

        def _on_finished(_name, control_info, exception):
            if exception is not None:
                callback(self.id, False, str(exception))
                return

            self._control_info = control_info

            try:
                info = {
                    'connection_string': "direct",
                    'uuid': control_info.uuid,
                    'signal_strength': 100
                }

                self._trigger_callback('on_scan', self.id, info, self.ExpirationTime)
            finally:
                callback(self.id, True, None)

        self._control_thread.command(JLinkControlThread.FIND_CONTROL, _on_finished, self._device_info.ram_start, self._device_info.ram_size)

    def debug_async(self, conn_id, cmd_name, cmd_args, progress_callback, callback):
        """Asynchronously complete a named debug command.

        The command name and arguments are passed to the underlying device adapter
        and interpreted there.  If the command is long running, progress_callback
        may be used to provide status updates.  Callback is called when the command
        has finished.

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            cmd_name (string): the name of the debug command we want to invoke
            cmd_args (dict): any arguments that we want to send with this command.
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)
            callback (callable): A callback for when we have finished the debug command, called as:
                callback(connection_id, adapter_id, success, retval, failure_reason)
                'connection_id': the connection id
                'adapter_id': this adapter's id
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
                'retval': A command specific dictionary of return value information
        """

        known_commands = {
            'dump_ram': JLinkControlThread.DUMP_ALL_RAM,
            'program_flash': JLinkControlThread.PROGRAM_FLASH,
        }

        cmd_code = known_commands.get(cmd_name)
        if cmd_code is None:
            callback(conn_id, self.id, False, None, "Unsupported command: %s" % cmd_name)

        def _on_finished(_name, retval, exception):
            if exception is not None:
                callback(conn_id, self.id, False, None, str(exception))
                return

            callback(conn_id, self.id, True, retval, None)

        self._control_thread.command(cmd_code, _on_finished, self._device_info, self._control_info, cmd_args, progress_callback)

    def connect_async(self, connection_id, connection_string, callback):
        """Connect to a device by its connection_string

        This function asynchronously connects to a device by its BLE address
        passed in the connection_string parameter and calls callback when
        finished.  Callback is called on either success or failure with the
        signature:

        callback(conection_id, adapter_id, success: bool, failure_reason: string or None)

        Args:
            connection_string (string): A unique connection string that identifies
                which device to connect to, if many are possible.
            connection_id (int): A unique integer set by the caller for
                referring to this connection once created
            callback (callable): A callback function called when the
                connection has succeeded or failed
        """
        self._try_connect(connection_string)

        def _on_finished(_name, control_info, exception):
            if exception is not None:
                callback(connection_id, self.id, False, str(exception))
                return

            if control_info is not None:
                self._control_info = control_info

            callback(connection_id, self.id, True, None)
            self._connection_id = connection_id

        self._control_thread.command(JLinkControlThread.VERIFY_CONTROL, _on_finished, self._device_info, self._control_info)

    def _open_rpc_interface(self, conn_id, callback):
        """Enable RPC interface for this IOTile device

        Args:
            conn_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        callback(conn_id, self.id, True, None)

    def _open_script_interface(self, conn_id, callback):
        """Enable script streaming interface for this IOTile device

        Args:
            conn_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        callback(conn_id, self.id, True, None)

    def _open_debug_interface(self, conn_id, callback, connection_string=None):
        """Enable debug interface for this IOTile device

        Args:
            conn_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """
        self._try_connect(connection_string)
        callback(conn_id, self.id, True, None)

    def periodic_callback(self):
        """Periodic cleanup tasks to maintain this adapter."""

        pass

    def send_rpc_async(self, conn_id, address, rpc_id, payload, timeout, callback):
        """Asynchronously send an RPC to this IOTile device.

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            address (int): the addres of the tile that we wish to send the RPC to
            rpc_id (int): the 16-bit id of the RPC we want to call
            payload (bytearray): the payload of the command
            timeout (float): the number of seconds to wait for the RPC to execute
            callback (callable): A callback for when we have finished the RPC.  The callback will be called as"
                callback(connection_id, adapter_id, success, failure_reason, status, payload)
                'connection_id': the connection id
                'adapter_id': this adapter's id
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
                'status': the one byte status code returned for the RPC if success == True else None
                'payload': a bytearray with the payload returned by RPC if success == True else None
        """

        def _on_finished(_name, retval, exception):
            if exception is not None:
                callback(conn_id, self.id, False, str(exception), None, None)
                return

            callback(conn_id, self.id, True, None, retval['status'], retval['payload'])

        # Default to polling for the response every 1 millisecond
        # FIXME, add an exponential polling backoff so that we wait 1, 2, 4, 8, etc ms
        self._control_thread.command(JLinkControlThread.SEND_RPC, _on_finished, self._device_info, self._control_info, address, rpc_id, payload, 0.001, timeout)

    def send_script_async(self, conn_id, data, progress_callback, callback):
        """Asynchronously send a a script to this IOTile device

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            data (string): the script to send to the device
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)
            callback (callable): A callback for when we have finished sending the script.  The callback will be called as"
                callback(connection_id, adapter_id, success, failure_reason)
                'connection_id': the connection id
                'adapter_id': this adapter's id
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
        """

        def _on_finished(_name, _retval, exception):
            if exception is not None:
                callback(conn_id, self.id, False, str(exception))
                return

            callback(conn_id, self.id, True, None)

        self._control_thread.command(JLinkControlThread.SEND_SCRIPT, _on_finished, self._device_info, self._control_info, data, progress_callback)
