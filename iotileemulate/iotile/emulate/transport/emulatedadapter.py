"""Subclass of VirtualDeviceAdapter that supports emulated devices.

This DeviceAdapter provides additional DebugManager functionality such as
saving and loading internal state snapshots and loading test scenarios
into the emulated devices.
"""

import logging
from iotile.core.hw.transport.virtualadapter import VirtualDeviceAdapter
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

        device = self.connections.get(conn_id)

        if device is None:
            callback(conn_id, self.id, False, None, 'Could not find connection to device.')
            return

        success = True
        reason = None
        retval = None

        try:
            if cmd_name == 'dump_state':
                retval = device.dump_state()
            elif cmd_name == 'restore_state':
                state = cmd_args['snapshot']
                device.restore_state(state)
            elif cmd_name == 'load_scenario':
                scenario = cmd_args['scenario']
                device.load_metascenario(scenario)
            elif cmd_name == 'track_changes':
                if cmd_args['enabled']:
                    device.state_history.enable()
                else:
                    device.state_history.disable()
            elif cmd_name == 'dump_changes':
                outpath = cmd_args['path']
                device.state_history.dump(outpath)
            else:
                success = False
                reason = "Unknown command %s" % cmd_name
        except Exception as exc:  #pylint:disable=broad-except;We need to turn all exceptions into a callback
            self._logger.exception("Error processing debug command %s: args=%s", cmd_name, cmd_args)
            success = False
            reason = "Exception %s occurred during processing" % str(exc)

        callback(conn_id, self.id, success, retval, reason)

    def _open_debug_interface(self, conn_id, callback, connection_string=None):
        """Enable debug interface for this IOTile device

        Args:
            conn_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(conn_id, adapter_id, success, failure_reason)
        """

        callback(conn_id, self.id, True, None)

    def periodic_callback(self):
        """Periodic callback task.

        This task is called periodically when this device adapter is attached
        to an iotile-gateway and called at specific points in time when it
        is attached to an AdapterStream.

        The primary task that we need to do for emulated devices is to call
        wait_idle() to make sure that they finish any pending background work.

        This is particularly useful for ensuring that reset RPCs happen
        synchronously without needing a delay.
        """

        super(EmulatedDeviceAdapter, self).periodic_callback()

        for dev in self.devices.values():
            dev.wait_idle()
