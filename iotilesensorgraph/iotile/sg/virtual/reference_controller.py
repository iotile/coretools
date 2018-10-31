"""A reference implementation of the iotile controller that allows update verification."""

from __future__ import print_function, absolute_import, unicode_literals
import logging
from iotile.core.hw.virtual import EmulatedTile, tile_rpc
from iotile.core.exceptions import ArgumentError
from .feature_mixins import RemoteBridgeMixin, TileManagerMixin


class ReferenceController(RemoteBridgeMixin, TileManagerMixin, EmulatedTile):
    """A reference iotile controller implementation.

    This tile implements the major behavior of an IOTile controller including
    setting and inspecting sensorgraphs as well as setting and inspecting user
    keys and app/os tags.  The default reference implementation does not do
    anything with set data except expose it on public properties so that we
    can verify what was done to the device.

    Args:
        address (int): The address of this tile in the VirtualIOTIleDevice
            that contains it
        args (dict): The arguments to use to create this tile.  The currently supported
            arguments are:
                name (str): The 6 character name that should be returned when this
                    tile is asked for its status to allow matching it with a proxy
                    object.
        device (TileBasedVirtualDevice) : optional, device on which this tile is running
    """

    STATE_NAME = "reference_controller"
    STATE_VERSION = "0.1.0"

    def __init__(self, address, args, device=None):
        name = args.get('name', 'refcn1')
        self._device = device
        self._logger = logging.getLogger(__name__)

        EmulatedTile.__init__(self, address, name, device)

        # Initialize all of the controller subsystems
        RemoteBridgeMixin.__init__(self)
        TileManagerMixin.__init__(self)

        self.sensor_graph = {
            "nodes": [],
            "streamers": [],
            "constants": []
        }

        self.app_info = (0, "0.0")
        self.os_info = (0, "0.0")

    def dump_state(self):
        """Dump the current state of this emulated object as a dictionary.

        Returns:
            dict: The current state of the object that could be passed to load_state.
        """

        superstate = super(ReferenceController, self).dump_state()

        superstate.update({
            'state_name': self.STATE_NAME,
            'state_version': self.STATE_VERSION,
            'app_info': self.app_info,
            'os_info': self.os_info,

            # Dump all of the subsystems
            'remote_bridge': self.remote_bridge.dump()
        })

        return superstate

    def restore_state(self, state):
        """Restore the current state of this emulated object.

        Args:
            state (dict): A previously dumped state produced by dump_state.
        """

        super(ReferenceController, self).restore_state(state)

        state_name = state.get('state_name')
        state_version = state.get('state_version')

        if state_name != self.STATE_NAME or state_version != self.STATE_VERSION:
            raise ArgumentError("Invalid emulated device state name or version", found=(state_name, state_version),
                                expected=(self.STATE_NAME, self.STATE_VERSION))

        self.app_info = state.get('app_info', (0, "0.0"))
        self.os_info = state.get('os_info', (0, "0.0"))

        # Restore all of the subsystems
        self.remote_bridge.restore(state.get('remote_bridge', {}))

    @tile_rpc(1, "", "")
    def reset(self):
        """Reset the device."""

        self._device.reset_count += 1
        return []

    @tile_rpc(0x1008, "", "L8xLL")
    def controller_info(self):
        """Get the controller UUID, app tag and os tag."""

        return [self._device.iotile_id, _pack_version(*self.os_info), _pack_version(*self.app_info)]


def _pack_version(tag, version):
    if tag >= (1 << 20):
        raise ArgumentError("The tag number is too high.  It must fit in 20-bits", max_tag=1 << 20, tag=tag)

    if "." not in version:
        raise ArgumentError("You must pass a version number in X.Y format", version=version)

    major, _, minor = version.partition('.')
    try:
        major = int(major)
        minor = int(minor)
    except ValueError:
        raise ArgumentError("Unable to convert version string into major and minor version numbers", version=version)

    if major < 0 or minor < 0 or major >= (1 << 6) or minor >= (1 << 6):
        raise ArgumentError("Invalid version numbers that must be in the range [0, 63]", major=major, minor=minor, version_string=version)

    version_number = (major << 6) | minor
    combined_tag = (version_number << 20) | tag
    return combined_tag
