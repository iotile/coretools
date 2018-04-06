"""A reference implementation of the iotile controller that allows update verification."""

from __future__ import print_function, absolute_import, unicode_literals
import logging
from iotile.core.hw.virtual import VirtualTile, tile_rpc
from iotile.core.hw.update import UpdateScript
from iotile.core.exceptions import ArgumentError
from iotile.sg.update import *
from iotile.core.hw.update.records import *

class BRIDGE_STATUS(object):
    IDLE = 0
    WAITING = 1
    RECEIVING = 2
    RECEIVED = 3
    VALIDATED = 4
    EXECUTING = 5


class ReferenceController(VirtualTile):
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

    def __init__(self, address, args, device=None):
        name = args.get('name', 'refcn1')

        super(ReferenceController, self).__init__(address, name, device)

        self.sensor_graph = {
            "nodes": [],
            "streamers": [],
            "constants": []
        }

        self.app_info = (0, "0.0")
        self.os_info = (0, "0.0")

        self.bridge_status = BRIDGE_STATUS.IDLE
        self.bridge_error = 0
        self.parsed_script = None
        self.script_error = None

        self._device = device
        self._logger = logging.getLogger(__name__)

    @tile_rpc(0x2100, "", "L")
    def begin_script(self):
        """Indicate we are going to start loading a script."""

        if self.bridge_status in (BRIDGE_STATUS.RECEIVED, BRIDGE_STATUS.VALIDATED, BRIDGE_STATUS.EXECUTING):
            return [1]  #FIXME: Return correct error here

        self.bridge_status = BRIDGE_STATUS.WAITING
        self.bridge_error = 0
        self.script_error = None
        self.parsed_script = None

        self._device.script = bytearray()

        return [0]

    @tile_rpc(0x2102, "", "L")
    def end_script(self):
        """Indicate that we have finished receiving a script."""

        if self.bridge_status not in (BRIDGE_STATUS.RECEIVED, BRIDGE_STATUS.WAITING):
            return [1] #FIXME: State change

        self.bridge_status = BRIDGE_STATUS.RECEIVED
        return [0]

    def _run_script(self):
        """Actually run an UpdateScript."""

        for record in self.parsed_script.records:
            pass

    @tile_rpc(0x2103, "", "L")
    def trigger_script(self):
        """Actually process a script."""

        if self.bridge_status not in (BRIDGE_STATUS.RECEIVED,):
            return [1] #FIXME: State change

        # This is asynchronous in real life so just cache the error
        try:
            self.parsed_script = UpdateScript.FromBinary(self._device.script)
            #self._run_script()

            self.bridge_status = BRIDGE_STATUS.IDLE
        except Exception as exc:
            self._logger.exception("Error parsing script streamed to device")
            self.script_error = exc
            self.bridge_error = 1 # FIXME: Error code

        return [0]

    @tile_rpc(0x2104, "", "LL")
    def query_status(self):
        """Get the status and last error."""

        return [self.bridge_status, self.bridge_error]

    @tile_rpc(0x2105, "", "L")
    def reset_script(self):
        """Clear any partially received script."""

        self.bridge_status = BRIDGE_STATUS.IDLE
        self.bridge_error = 0
        self.parsed_script = None
        self._device.script = bytearray()

        return [0]

    @classmethod
    def _pack_version(cls, tag, version):
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

    @tile_rpc(1, "", "")
    def reset(self):
        """Reset the device."""

        self._device.reset_count += 1
        return []

    @tile_rpc(0x1008, "", "L8xLL")
    def controller_info(self):
        """Get the controller UUID, app tag and os tag."""

        return [self._device.iotile_id, self._pack_version(*self.os_info), self._pack_version(*self.app_info)]
