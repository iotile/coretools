"""Subclass of VirtualDeviceAdapter that supports emulated devices.

This DeviceAdapter provides additional DebugManager functionality such as
saving and loading internal state snapshots and loading test scenarios
into the emulated devices.
"""

import logging
from iotile.core.hw.transport import VirtualDeviceAdapter
from iotile.core.hw.exceptions import DeviceAdapterError
from ..virtual import EmulatedDevice


class EmulatedDeviceAdapter(VirtualDeviceAdapter):
    """DeviceAdapter for connecting to EmulatedDevices.

    This adapter is used the exact same way as VirtualDeviceAdapter, except
    that it only supported EmulatedDevice subclasses and it implements the
    debug interface to allow for dumping and loading the state of the
    emulated device.

    Args:
        port (string): A port description that should be in the form of
            device_name1@<optional_config_json1;device_name2@optional_config_json2
        devices (list of EmulatedDevice): Optional list of specific, precreated emulated
            devices that should be added to the device adapter.
    """

    def __init__(self, port, devices=None):
        super(EmulatedDeviceAdapter, self).__init__(port, devices)
        self._logger = logging.getLogger(__name__)

    @classmethod
    def _validate_device(cls, device):
        """Hook for subclases to ensure that only specific kinds of devices are loaded.

        Returns:
            bool: Whether the virtual device is allowed to load.
        """

        return isinstance(device, EmulatedDevice)

    async def send_rpc(self, conn_id, address, rpc_id, payload, timeout):
        """Asynchronously send an RPC to this IOTile device

        Args:
            conn_id (int): A unique identifier that will refer to this connection
            address (int): the address of the tile that we wish to send the RPC to
            rpc_id (int): the 16-bit id of the RPC we want to call
            payload (bytearray): the payload of the command
            timeout (float): the number of seconds to wait for the RPC to execute
        """

        try:
            return await super(EmulatedDeviceAdapter, self).send_rpc(conn_id, address, rpc_id, payload, timeout)
        finally:
            for dev in self.devices.values():
                await dev.wait_idle()

    async def debug(self, conn_id, name, cmd_args):
        """Asynchronously complete a named debug command.

        The command name and arguments are passed to the underlying device adapter
        and interpreted there.

        Args:
            conn_id (int): A unique identifer that will refer to this connection
            name (string): the name of the debug command we want to invoke
            cmd_args (dict): any arguments that we want to send with this command.
        """


        device = self._get_property(conn_id, 'device')

        retval = None

        try:
            if name == 'dump_state':
                retval = device.dump_state()
            elif name == 'restore_state':
                state = cmd_args['snapshot']
                device.restore_state(state)
            elif name == 'load_scenario':
                scenario = cmd_args['scenario']
                device.load_metascenario(scenario)
            elif name == 'track_changes':
                if cmd_args['enabled']:
                    device.state_history.enable()
                else:
                    device.state_history.disable()
            elif name == 'dump_changes':
                outpath = cmd_args['path']
                device.state_history.dump(outpath)
            else:
                reason = "Unknown command %s" % name
                raise DeviceAdapterError(conn_id, 'debug {}'.format(name), reason)
        except Exception as exc:
            self._logger.exception("Error processing debug command %s: args=%s", name, cmd_args)
            reason = "Exception %s occurred during processing" % str(exc)
            raise DeviceAdapterError(conn_id, 'debug {}'.format(name), reason) from exc

        return retval
