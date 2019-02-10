"""Mixin for device updating via signed scripts."""

import base64
from iotile.core.hw.virtual import tile_rpc
from iotile.core.hw.update import UpdateScript
from ...virtual import SerializableState
from .controller_system import ControllerSubsystemBase


# FIXME: Move this to constants section
class BRIDGE_STATUS(object):
    """Enum for valid remote bridge statuses."""
    IDLE = 0
    WAITING = 1
    RECEIVING = 2
    RECEIVED = 3
    VALIDATED = 4
    EXECUTING = 5


class RemoteBridgeState(SerializableState, ControllerSubsystemBase):
    """Serializeable state object for all remote bridge state.

    Note that the script_error property is just a convenience property
    for looking at internal exceptions when executing scripts.  It does
    not reflect a real emulated device state and is not dumped or restored
    when dump() or restore() is called.
    """

    def __init__(self, emulator):
        ControllerSubsystemBase.__init__(self, emulator)
        SerializableState.__init__(self)

        self.status = BRIDGE_STATUS.IDLE
        self.error = 0
        self.parsed_script = None
        self.script_error = None

        self.mark_ignored('initialized')
        self.mark_complex('parsed_script', self._dump_script, self._restore_script)

    def clear_to_reset(self, config_vars):
        """Clear the RemoteBridge subsystem to its reset state."""

        super(RemoteBridgeState, self).clear_to_reset(config_vars)
        self.status = BRIDGE_STATUS.IDLE
        self.error = 0

    def _dump_script(self, value):
        if value is None:
            return None

        encoded = value.encode()
        return base64.b64encode(encoded).decode('utf-8')

    @classmethod
    def _restore_script(cls, b64encoded):
        if b64encoded is None:
            return None

        encoded = base64.b64decode(b64encoded)
        return UpdateScript.FromBinary(encoded)


class RemoteBridgeMixin(object):
    """Reference controller subsystem for device updating.

    This class must be used as a mixin with a ReferenceController base class.
    """


    def __init__(self, emulator):
        self.remote_bridge = RemoteBridgeState(emulator)
        self._post_config_subsystems.append(self.remote_bridge)

    @tile_rpc(0x2100, "", "L")
    def begin_script(self):
        """Indicate we are going to start loading a script."""

        if self.remote_bridge.status in (BRIDGE_STATUS.RECEIVED, BRIDGE_STATUS.VALIDATED, BRIDGE_STATUS.EXECUTING):
            return [1]  #FIXME: Return correct error here

        self.remote_bridge.status = BRIDGE_STATUS.WAITING
        self.remote_bridge.error = 0
        self.remote_bridge.script_error = None
        self.remote_bridge.parsed_script = None

        self._device.script = bytearray()

        return [0]

    @tile_rpc(0x2102, "", "L")
    def end_script(self):
        """Indicate that we have finished receiving a script."""

        if self.remote_bridge.status not in (BRIDGE_STATUS.RECEIVED, BRIDGE_STATUS.WAITING):
            return [1] #FIXME: State change

        self.remote_bridge.status = BRIDGE_STATUS.RECEIVED
        return [0]

    @tile_rpc(0x2103, "", "L")
    def trigger_script(self):
        """Actually process a script."""

        if self.remote_bridge.status not in (BRIDGE_STATUS.RECEIVED,):
            return [1] #FIXME: State change

        # This is asynchronous in real life so just cache the error
        try:
            self.remote_bridge.parsed_script = UpdateScript.FromBinary(self._device.script)
            #FIXME: Actually run the script

            self.remote_bridge.status = BRIDGE_STATUS.IDLE
        except Exception as exc:
            self._logger.exception("Error parsing script streamed to device")
            self.remote_bridge.script_error = exc
            self.remote_bridge.error = 1 # FIXME: Error code

        return [0]

    @tile_rpc(0x2104, "", "LL")
    def query_status(self):
        """Get the status and last error."""

        return [self.remote_bridge.status, self.remote_bridge.error]

    @tile_rpc(0x2105, "", "L")
    def reset_script(self):
        """Clear any partially received script."""

        self.remote_bridge.status = BRIDGE_STATUS.IDLE
        self.remote_bridge.error = 0
        self.remote_bridge.parsed_script = None
        self._device.script = bytearray()

        return [0]
