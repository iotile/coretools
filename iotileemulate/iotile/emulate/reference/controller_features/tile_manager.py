"""Mixin for device updating via signed scripts."""

import base64
from iotile.core.hw.virtual import tile_rpc
from ...virtual import SerializableState
from ...constants import RunLevel, TileState, rpcs
from .controller_system import ControllerSubsystemBase


class TileInfo(SerializableState):
    def __init__(self, hw_type, name, api_info, fw_info, exec_info, slot, unique_id, state=TileState.INVALID, address=None):
        super(TileInfo, self).__init__()

        self.hw_type = hw_type
        self.name = name
        self.api_info = api_info
        self.fw_info = fw_info
        self.exec_info = exec_info
        self.slot = slot
        self.unique_id = unique_id

        self.state = state
        self.address = address

        self.mark_complex('name', self._dump_name, self._restore_name)

    def _dump_name(self, name):
        return base64.b64encode(name).decode('utf-8')

    def _restore_name(self, name):
        return base64.b64decode(name)

    def registration_packet(self):
        """Serialize this into a tuple suitable for returning from an RPC.

        Returns:
            tuple: The serialized values.
        """

        return (self.hw_type, self.api_info[0], self.api_info[1], self.name, self.fw_info[0], self.fw_info[1], self.fw_info[2],
                self.exec_info[0], self.exec_info[0], self.exec_info[0], self.slot, self.unique_id)

    @classmethod
    def CreateInvalid(cls):
        """Create a blank invalid TileInfo structure.

        Returns:
            TileInfo
        """

        return TileInfo(0, '\0'*6, (0, 0), (0, 0, 0), (0, 0, 0), 0, 0)


class TileManagerState(SerializableState, ControllerSubsystemBase):
    """Serializeable state object for all tile_manager state."""

    def __init__(self, emulator):
        SerializableState.__init__(self)
        ControllerSubsystemBase.__init__(self, emulator)

        self.registered_tiles = []
        self.safe_mode = False
        self.debug_mode = False
        self.queue = emulator.create_queue(register=True)

        self.mark_ignored('initialized')
        self.mark_ignored('queue')
        self.mark_complex('registered_tiles', self._dump_registered_tiles, self._restore_registered_tiles)

    async def _reset_vector(self):
        self.initialized.set()

        while True:
            info, config_rpcs = await self.queue.get()

            try:
                for rpc in config_rpcs:
                    await self._emulator.await_rpc(*rpc)

                await self._emulator.await_rpc(info.address, rpcs.START_APPLICATION)

                info.state = TileState.RUNNING
            finally:
                self.queue.task_done()

    def clear_to_reset(self, config_vars):
        """Clear to the state immediately after a reset."""

        super(TileManagerState, self).clear_to_reset(config_vars)
        self.registered_tiles = self.registered_tiles[:1]
        self.safe_mode = False
        self.debug_mode = False

    def _dump_registered_tiles(self, tiles):
        return [info.dump() for info in tiles]

    def _restore_registered_tiles(self, serialized_tiles):
        tiles = []

        for serialized_tile in serialized_tiles:
            tile = TileInfo(None, None, None, None, None, None, None)
            tile.restore(serialized_tile)

            tiles.append(tile)

        return tiles

    def insert_tile(self, tile_info):
        """Add or replace an entry in the tile cache.

        Args:
            tile_info (TileInfo): The newly registered tile.
        """

        for i, tile in enumerate(self.registered_tiles):
            if tile.slot == tile_info.slot:
                self.registered_tiles[i] = tile_info
                return

        self.registered_tiles.append(tile_info)


class TileManagerMixin(object):
    """Reference controller subsystem for device updating.

    This class must be used as a mixin with a ReferenceController base class.
    """


    def __init__(self, emulator):
        self.tile_manager = TileManagerState(emulator)

        # Register the controller itself into our tile_info database
        info = TileInfo(self.hardware_type, self.name, self.api_version, self.firmware_version, self.executive_version, 0, 0, state=TileState.RUNNING)
        self.tile_manager.insert_tile(info)

        self._post_config_subsystems.append(self.tile_manager)

    @tile_rpc(*rpcs.REGISTER_TILE)
    def register_tile(self, hw_type, api_major, api_minor, name, fw_major, fw_minor, fw_patch, exec_major, exec_minor, exec_patch, slot, unique_id):
        """Register a tile with this controller.

        This function adds the tile immediately to its internal cache of registered tiles
        and queues RPCs to send all config variables and start tile rpcs back to the tile.
        """

        api_info = (api_major, api_minor)
        fw_info = (fw_major, fw_minor, fw_patch)
        exec_info = (exec_major, exec_minor, exec_patch)

        address = 10 + slot
        info = TileInfo(hw_type, name, api_info, fw_info, exec_info, slot, unique_id, state=TileState.JUST_REGISTERED, address=address)

        self.tile_manager.insert_tile(info)

        debug = int(self.tile_manager.debug_mode)

        if self.tile_manager.safe_mode:
            run_level = RunLevel.SAFE_MODE
            info.state = TileState.SAFE_MODE
            config_rpcs = []
        else:
            run_level = RunLevel.START_ON_COMMAND
            info.state = TileState.BEING_CONFIGURED
            config_rpcs = self.config_database.stream_matching(address, name)

        self.tile_manager.queue.put_nowait((info, config_rpcs))

        return [address, run_level, debug]

    @tile_rpc(*rpcs.COUNT_TILES)
    def count_tiles(self):
        """Count the number of registered tiles including the controller."""

        return [len(self.tile_manager.registered_tiles)]

    @tile_rpc(*rpcs.DESCRIBE_TILE)
    def describe_tile(self, index):
        """Get the registration information for the tile at the given index."""

        if index >= len(self.tile_manager.registered_tiles):
            tile = TileInfo.CreateInvalid()
        else:
            tile = self.tile_manager.registered_tiles[index]

        return tile.registration_packet()
