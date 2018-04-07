"""A reference device with properties for inspecting what has been set by update scripts."""

from iotile.core.hw.virtual import VirtualIOTileDevice
from .reference_controller import ReferenceController


class ReferenceDevice(VirtualIOTileDevice):
    """A reference implementation of an IOTile device.

    This is useful for testing the effects of updates and other build
    automation processes.

    Args:
        args (dict): A dictionary of optional creation arguments.  Currently
            supported are:
                iotile_id (int or hex string): The id of this device. This
                defaults to 1 if not specified.
    """

    def __init__(self, args):
        iotile_id = args.get('iotile_id', 1)

        if isinstance(iotile_id, str):
            iotile_id = int(iotile_id, 16)

        super(ReferenceDevice, self).__init__(iotile_id, 'refcn1')

        self.controller = ReferenceController(8, {'name':'refcn1'}, device=self)
        self.add_tile(8, self.controller)
        self.reset_count = 0
