""" helper device for test in test_busyresponse.py """

import asyncio
import logging
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.hw.proxy import TileBusProxyObject
from iotile.core.hw.virtual.common_types import AsynchronousRPCResponse, pack_rpc_payload
from iotile.core.hw.virtual import tile_rpc
from iotile.emulate.virtual import EmulatedPeripheralTile
from iotile.emulate.reference import ReferenceDevice
from typedargs.annotate import docannotate, context

NUMBER_TILE1 = 11
NUMBER_TILE2 = 12

ACTION_RPC_Y = "rpc_y"
ACTION_RPC_X = "rpc_x"

class EmulatedTile1(EmulatedPeripheralTile):
    """Tile 1 has a rpc RPC Y that triggers async rpc in Tile 2"""

    name = b'tile01'

    def __init__(self, address, device):
        super(EmulatedTile1, self).__init__(address, device)
        self._work = device.emulator.create_queue(register=False)
        self._logger = logging.getLogger(__name__)

    async def _application_main(self):
        self.initialized.set()

        while True:
            action, args = await self._work.get()

            try:
                if action == ACTION_RPC_Y:
                    await self._device.emulator.await_rpc(NUMBER_TILE2, 0x8000, resp_format="5s")

            except:#pylint:disable=bare-except;
                self._logger.exception('exception in tile {}'.format(self.name))

    @tile_rpc(0x800a, "", "15s")
    def sync_rpc(self):
        return [b'sync rpc tile01']

    @tile_rpc(0x8000, "", "")
    def rpc_y(self):
        """Make an async rpc in the second tile"""
        self._work.put_nowait((ACTION_RPC_Y, (0x8000,)))
        return []

    @tile_rpc(0x8001, "", "")
    def set_event(self):
        self._device.event_flag.set()
        return []


class EmulatedTile2(EmulatedPeripheralTile):
    """Tile 2 has a rpc RPC X that wait till an event flag will be set"""

    name = b'tile02'

    def __init__(self, address, device):
        super(EmulatedTile2, self).__init__(address, device)
        self._work = device.emulator.create_queue(register=False)
        self._logger = logging.getLogger(__name__)

    async def _application_main(self):
        self.initialized.set()

        while True:
            action, args = await self._work.get()
            rpc_id, = args

            try:
                if action == ACTION_RPC_X:
                    await self._device.event_flag.wait()
                    self._device.emulator.finish_async_rpc(self.address, rpc_id, b"rpc x")

                else:
                    self._logger.error("Unknown action in main loop: %s", action)

            except:#pylint:disable=bare-except;
                self._logger.exception("Error processing background action: action=%s, args=%s", action, args)


    @tile_rpc(0x800a, "", "15s")
    def sync_rpc(self):
        return [b'sync rpc tile02']

    @tile_rpc(0x8000, "", "5s")
    def rpc_x(self):
        self._work.put_nowait((ACTION_RPC_X, (0x8000,)))
        raise AsynchronousRPCResponse()


class EmulatedDevice(ReferenceDevice):
    """Emulated device with 2 emulated peripheral tiles: 1 and 2"""
    def __init__(self, args):
        super(EmulatedDevice, self).__init__(args)

        tile1 = EmulatedTile1(NUMBER_TILE1, self)
        tile2 = EmulatedTile2(NUMBER_TILE2, self)

        self.add_tile(NUMBER_TILE1, tile1)
        self.add_tile(NUMBER_TILE2, tile2)

        # RPC X in Tile 2 waits till this flag will be set
        self.event_flag = self.emulator.create_event()


@context("EmulatedTile1")
class EmulatedTileProxy1(TileBusProxyObject):
    @classmethod
    def ModuleName(cls):
        return 'tile01'

    @docannotate
    def rpc_y(self):
        """ Calls respectively rpc x in tile 2 """
        self.rpc_v2(0x8000, "", "")

    @docannotate
    def set_event(self):
        """ Sets flag for tile 2 """
        self.rpc_v2(0x8001, "", "")

    @docannotate
    def sync_rpc(self):
        """
        Synchronous rpc
        Returns:
            str:
        """
        data, = self.rpc_v2(0x800a, "", "15s")
        return data


@context("EmulatedTile2")
class EmulatedTileProxy2(TileBusProxyObject):
    @classmethod
    def ModuleName(cls):
        return 'tile02'

    @docannotate
    def rpc_x(self):
        """ Waits asynchronously for self._device.event_flag """
        self.rpc_v2(0x8000, "", "")

    @docannotate
    def sync_rpc(self):
        """
        Synchronous rpc
        Returns:
            str:
        """
        data, = self.rpc_v2(0x800a, "", "15s")
        return data
