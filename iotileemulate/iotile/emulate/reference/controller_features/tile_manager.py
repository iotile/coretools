"""Mixin for device updating via signed scripts."""

from future.utils import viewitems
from iotile.core.hw.virtual import tile_rpc
from ...virtual import SerializableState
from ...constants import RunLevel, TileState, rpcs

class TileInfo(SerializableState):
    def __init__(self, hw_type, name, api_info, fw_info, exec_info, slot, unique_id, state=TileState.INVALID):
        super(TileInfo, self).__init__()

        self.hw_type = hw_type
        self.name = name
        self.api_info = api_info
        self.fw_info = fw_info
        self.exec_info = exec_info
        self.slot = slot
        self.unique_id = unique_id
        self.state = state


class TileManagerState(SerializableState):
    """Serializeable state object for all tile_manager state."""

    def __init__(self):
        super(TileManagerState, self).__init__()

        self.registered_tiles = {}
        self.safe_mode = False
        self.debug_mode = False

        self.mark_complex('registered_tiles', self._dump_registered_tiles, self._restore_registered_tiles)

    def _dump_registered_tiles(self, tiles):
        return {address: info.dump() for address, info in viewitems(tiles)}

    def _restore_registered_tiles(self, serialized_tiles):
        tiles = {}

        for address, serialized_tile in viewitems(serialized_tiles):
            address = int(address)

            tile = TileInfo(None, None, None, None, None, None, None)
            tile.restore(serialized_tile)

            tiles[address] = tile

        return tiles


class TileManagerMixin(object):
    """Reference controller subsystem for device updating.

    This class must be used as a mixin with a ReferenceController base class.
    """


    def __init__(self):
        self.tile_manager = TileManagerState()

    @tile_rpc(*rpcs.REGISTER_TILE)
    def register_tile(self, hw_type, api_major, api_minor, name, fw_major, fw_minor, fw_patch, exec_major, exec_minor, exec_patch, slot, unique_id):
        """Register a tile with this controller.

        This function adds the tile immediately to its internal cache of registered tiles
        and queues RPCs to send all config variables and start tile rpcs back to the tile.
        """

        api_info = (api_major, api_minor)
        fw_info = (fw_major, fw_minor, fw_patch)
        exec_info = (exec_major, exec_minor, exec_patch)

        info = TileInfo(hw_type, name, api_info, fw_info, exec_info, slot, unique_id, state=TileState.JUST_REGISTERED)
        address = 10 + slot

        self.tile_manager.registered_tiles[address] = info

        debug = int(self.tile_manager.debug_mode)

        if self.tile_manager.safe_mode:
            run_level = RunLevel.SAFE_MODE
            info.state = TileState.SAFE_MODE
        else:
            run_level = RunLevel.START_ON_COMMAND
            info.state = TileState.BEING_CONFIGURED

            # Stream any matching config variables to this tile
            config_rpcs = self.config_database.stream_matching(address, name)
            for rpc in config_rpcs:
                self._device.deferred_rpc(*rpc)

            def _update_state(_response):
                info.state = TileState.RUNNING

            self._device.deferred_rpc(address, rpcs.START_APPLICATION, callback=_update_state)

        return [address, run_level, debug]
