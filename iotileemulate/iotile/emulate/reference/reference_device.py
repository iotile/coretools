"""A reference device with properties for inspecting what has been set by update scripts."""

import base64
import logging
import asyncio
from time import monotonic
from iotile.core.exceptions import ArgumentError, DataError
from ..virtual import EmulatedDevice, EmulatedPeripheralTile
from ..constants import rpcs, streams
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

    __NO_EXTENSION__ = True

    STATE_NAME = "reference_device"
    STATE_VERSION = "0.1.0"

    def __init__(self, args):
        iotile_id = args.get('iotile_id', 1)
        controller_name = args.get('controller_name', 'refcn1')

        if isinstance(iotile_id, str):
            iotile_id = int(iotile_id, 16)

        super(ReferenceDevice, self).__init__(iotile_id)

        self.controller = ReferenceController(8, {'name': controller_name}, device=self)
        self.add_tile(8, self.controller)
        self.reset_count = 0
        self._logger = logging.getLogger(__name__)
        self._simulating_time = args.get('simulate_time', True)
        self._accelerating_time = args.get('accelerate_time', False)

    async def _time_ticker(self):
        start = monotonic()
        counter = 0
        while self._simulating_time:
            self.controller.clock_manager.handle_tick()
            await self.emulator.wait_idle()

            counter += 1
            next_tick = start + counter
            if not self._accelerating_time:
                now = monotonic()

                while now < next_tick:
                    if not self._simulating_time:
                        return

                    step = min(next_tick - now, 0.1)
                    await asyncio.sleep(step)
                    now = monotonic()

        self._logger.debug("Time ticker task stopped due to _simulating_time flag cleared")

    def iter_tiles(self, include_controller=True):
        """Iterate over all tiles in this device in order.

        The ordering is by tile address which places the controller tile
        first in the list.

        Args:
            include_controller (bool): Include the controller tile in the
                results.

        Yields:
            int, EmulatedTile: A tuple with the tile address and tile object.
        """

        for address, tile in sorted(self._tiles.items()):
            if address == 8 and not include_controller:
                continue

            yield address, tile

    def start(self, channel=None):
        """Start this emulated device.

        This triggers the controller to call start on all peripheral tiles in
        the device to make sure they start after the controller does and then
        it waits on each one to make sure they have finished initializing
        before returning.

        Args:
            channel (IOTilePushChannel): the channel with a stream and trace
                routine for streaming and tracing data through a VirtualInterface
        """

        super(ReferenceDevice, self).start(channel)

        try:
            self.controller.start(channel)

            # Guarantee an initialization order so that our trace files are deterministic
            for address, tile in sorted(self._tiles.items()):
                if address == 8:
                    continue

                if not isinstance(tile, EmulatedPeripheralTile):
                    raise DataError("An emulated ReferenceDevice can only have a single controller and all other tiles must inherit from EmulatedPeripheralTile",
                                    address=address)

                tile.start(channel)

            async def _launch_tiles():
                await self.controller.reset()
                await asyncio.wait_for(self.controller.initialized.wait(), 2.0)

                # Note that we do not explicitly reset the tiles.
                # The controller resets all tiles in its reset method.
                for address, tile in sorted(self._tiles.items()):
                    if address == 8:
                        continue

                    await asyncio.wait_for(tile.initialized.wait(), 2.0)

            self.emulator.run_task_external(_launch_tiles())

            if self._simulating_time:
                self.emulator.add_task(None, self._time_ticker())
        except:
            self.stop()
            raise

    def stop(self):
        """Stop this emulated device."""

        self._simulating_time = False
        super(ReferenceDevice, self).stop()

    def dump_state(self):
        """Dump the current state of this emulated object as a dictionary.

        Note that dump_state happens synchronously in the emulation thread to
        avoid any race conditions with accessing data members and ensure a
        consistent view of all state data.

        Returns:
            dict: The current state of the object that could be passed to load_state.
        """

        # Dump the state of all of the tiles
        def _background_dump():
            state = super(ReferenceDevice, self).dump_state()

            state['state_name'] = self.STATE_NAME
            state['state_version'] = self.STATE_VERSION
            state['reset_count'] = self.reset_count
            state['received_script'] = base64.b64encode(self.script).decode('utf-8')

            return state

        return self.synchronize_task(_background_dump)

    def restore_state(self, state):
        """Restore the current state of this emulated device.

        Note that restore_state happens synchronously in the emulation thread
        to avoid any race conditions with accessing data members and ensure a
        consistent atomic restoration process.

        This method will block while the background restore happens.

        Args:
            state (dict): A previously dumped state produced by dump_state.
        """

        state_name = state.get('state_name')
        state_version = state.get('state_version')

        if state_name != self.STATE_NAME or state_version != self.STATE_VERSION:
            raise ArgumentError("Invalid emulated device state name or version", found=(state_name, state_version),
                                expected=(self.STATE_NAME, self.STATE_VERSION))

        def _background_restore():
            # Restore the state of all of the tiles
            super(ReferenceDevice, self).restore_state(state)

            self.reset_count = state.get('reset_count', 0)
            self.script = base64.b64decode(state.get('received_script'))

        self.synchronize_task(_background_restore)

    async def _open_streaming_interface(self):
        """Called when someone opens a streaming interface to the device.

        This method will automatically notify sensor_graph that there is a
        streaming interface opened.
        """

        await self.emulator.await_rpc(8, rpcs.SG_GRAPH_INPUT, 8, streams.COMM_TILE_OPEN)

    async def _close_streaming_interface(self):
        """Called when someone closes the streaming interface to the device.

        This method will automatically notify sensor_graph that there is a no
        longer a streaming interface opened.
        """

        await self.emulator.await_rpc(8, rpcs.SG_GRAPH_INPUT, 8, streams.COMM_TILE_CLOSED)
