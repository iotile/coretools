"""A reference device with properties for inspecting what has been set by update scripts."""

import base64
from past.builtins import basestring
from iotile.core.exceptions import ArgumentError
from iotile.core.hw.virtual import EmulatedDevice
from .reference_controller import ReferenceController


class ReferenceDevice(EmulatedDevice):
    """A reference implementation of an IOTile device.

    This is useful for testing the effects of updates and other build
    automation processes.

    Args:
        args (dict): A dictionary of optional creation arguments.  Currently
            supported are:
                iotile_id (int or hex string): The id of this device. This
                defaults to 1 if not specified.
    """

    STATE_NAME = "reference_device"
    STATE_VERSION = "0.1.0"

    def __init__(self, args):
        iotile_id = args.get('iotile_id', 1)
        controller_name = args.get('controller_name', 'refcn1')

        if isinstance(iotile_id, basestring):
            iotile_id = int(iotile_id, 16)

        super(ReferenceDevice, self).__init__(iotile_id, controller_name)

        self.controller = ReferenceController(8, {'name': controller_name}, device=self)
        self.add_tile(8, self.controller)
        self.reset_count = 0

    def dump_state(self):
        """Dump the current state of this emulated object as a dictionary.

        Returns:
            dict: The current state of the object that could be passed to load_state.
        """

        # Dump the state of all of the tiles
        state = super(ReferenceDevice, self).dump_state()

        state['state_name'] = self.STATE_NAME
        state['state_version'] = self.STATE_VERSION
        state['reset_count'] = self.reset_count
        state['received_script'] = base64.b64encode(self.script)

        return state

    def restore_state(self, state):
        """Restore the current state of this emulated device.

        Args:
            state (dict): A previously dumped state produced by dump_state.
        """

        state_name = state.get('state_name')
        state_version = state.get('state_version')

        if state_name != self.STATE_NAME or state_version != self.STATE_VERSION:
            raise ArgumentError("Invalid emulated device state name or version", found=(state_name, state_version),
                                expected=(self.STATE_NAME, self.STATE_VERSION))

        # Restore the state of all of the tiles
        super(ReferenceDevice, self).restore_state(state)

        self.reset_count = state.get('reset_count', 0)
        self.script = base64.b64decode(state.get('received_script'))
