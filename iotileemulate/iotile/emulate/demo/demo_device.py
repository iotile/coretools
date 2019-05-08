"""A simple emulated reference device that includes a demo non-controller tile.

The demo emulated Peripheral tile showcases the 4 kinds of things that you can
do on an EmulatedPeripheralTile:

- Normal synchronous RPCS: These are methods decorated with the
  @tile_rpc decorator and directly invocable using the `rpc` method on an
  EmulatedDevice or via a proxy class.  The methods are run in the
  EmulationLoop inside of the RPC dispatch task.

  They may not yield since they are not coroutines.  If they block the entire
  emulation loop will block until they finish.  For that reason, they should
  not block.

- Asynchronous RPCS: These are RPCs whose implementation requires that they
  return their result via a callback.  In physical IOTile devices this is
  usually because the operation requires an unbounded amount of time to
  complete, such as asking an external sensor for a value that could take many
  ms to respond.

  These RPCs are typically implemented by queuing work for a background task
  and then raising AsynchronousRPCResponse().  This notifies the RPC dispatch
  that the RPC will be returning its response later and allows for other RPCs
  to be dispatched in the meantime.

  A background worker task associated with this tile can then call
  EmulatedDevice.finish_async_rpc when it wants to complete the RPC call.

  From the point of view of the caller of the RPC, it will block until
  finish_async_rpc has been called with the response and it does not have any
  way to know whether the response was given immediately or via a callback to
  finish_async_rpc.  Put another way, RPCs are always synchronous from the
  caller's perspective.  It is just that sometimes you don't want to block the
  RPC dispatch during a long-running RPC so that other callers can send RPCs
  while your caller is still waiting for its response.

- Background Loops: In a physical tile, there is a single main loop and
  RPC handlers are invoked as interrupts.  In EmulatedPeripheralTile subclasses,
  the _application_main() coroutine is the equivalent of the main loop.

  It is launched when the tile starts and should loop forever.  It is canceled
  clenaly when the tile is reset and started again.  If you need to perform
  tasks periodically that are not related to any specific RPC, they should
  go inside your _application_main().  Similarly, if you support asynchronous
  rpcs, they should be implemented by queuing work that is processed by
  _application_main().

- Coroutine RPCs: For some RPCs it may be easier to implement them if they can
  await an object.  In this case the RPC never raises AsynchronousRPCResponse
  and still blocks the RPC dispatch thread until it finishes, it is just that
  you are allowed to `await` an object inside your implementation.

The DemoEmulatedTile class in this module shows an example of how to perform
each of these 4 things.  Note that for ease of implementation, peripheral
tiles are able to directly stream and trace data out of the EmulatedDevice
rather than needing to invoke an RPC on the controller to stream or trace on
their behalf.
"""

import asyncio
import logging
from iotile.core.hw.virtual import tile_rpc
from iotile.core.hw.exceptions import AsynchronousRPCResponse
from ..virtual import EmulatedPeripheralTile
from ..reference import ReferenceDevice


class DemoEmulatedTile(EmulatedPeripheralTile):
    """A basic emulated tile showing all of the things you can do.

    This demo tile has a trivial main loop that pulls work queued by RPCs and
    executes it.  It has several synchronous RPCs, one asynchronous RPC, an
    RPC implemented as a coroutine and an RPC that triggers the tile to trace
    a bunch of binary data.
    """

    name = b'emudmo'

    def __init__(self, address, device):
        super(DemoEmulatedTile, self).__init__(address, device)
        self.register_scenario('loaded_counter', self.load_counter)
        self._counter = 0
        self._work = device.emulator.create_queue(register=False)
        self._logger = logging.getLogger(__name__)

    async def _application_main(self):
        self.initialized.set()

        while True:
            action, args = await self._work.get()

            try:
                if action == 'echo':
                    rpc_id, arg = args
                    self._device.emulator.finish_async_rpc(self.address, rpc_id, "L", arg)
                elif action == 'trace':
                    byte_count = args
                    chunks = byte_count // 20
                    if byte_count % 20:
                        chunks += 1

                    for i in range(0, chunks):
                        chunk_length = min(byte_count - i*20, 20)
                        data = bytes(range(0, chunk_length))

                        self._logger.debug("Tracing chunk %d/%d (size=%d)", i + 1, chunks, chunk_length)

                        success = await self._device.trace(data)
                        if not success:
                            self._logger.error("Failure sending chunk %d, aborting", i)
                            break

                    if success:
                        self._logger.info("Finished sending %d chunks of tracing data", chunks)
                else:
                    self._logger.error("Unknown action in main loop: %s", action)
            except:
                self._logger.exception("Error processing background action: action=%s, args=%s", action, args)

    def load_counter(self, counter):
        """Load the counter value of this device."""
        self._counter = counter

    @tile_rpc(0x8000, "L", "L")
    def async_echo(self, arg):
        """Asynchronously echo the argument number."""

        self._work.put_nowait(('echo', (0x8000, arg)))
        raise AsynchronousRPCResponse()

    @tile_rpc(0x8001, "L", "L")
    def sync_echo(self, arg):
        """Synchronously echo the argument number."""

        return [arg]

    @tile_rpc(0x8002, "", "L")
    def counter(self):
        """A counter that increments everytime it is called."""

        value = self._counter
        self._counter += 1
        return [value]

    @tile_rpc(0x8003, "L", "")
    def start_trace(self, count):
        """Start tracing a given number of bytes."""

        self._work.put_nowait(('trace', count))
        return []

    @tile_rpc(0x8004, "L", "L")
    async def coroutine_echo(self, arg):
        """Wait for a small delay and then echo.

        This method shows an example of how to implement an RPC as a
        coroutine.
        """

        await asyncio.sleep(0.01)
        return [arg]


class DemoEmulatedDevice(ReferenceDevice):
    """A basic emulated device that includes a single blank tile in addition to the reference controller.

    The blank tile in slot 1 has module name emudmo and the following two config variables declared
    to allow for testing config variable usage and streaming:

    - 0x8000: uint32_t
    - 0x8001: uint8_t[16]

    Args:
        args (dict): A dictionary of optional creation arguments.  Currently
            supported are:
                iotile_id (int or hex string): The id of this device. This
                defaults to 1 if not specified.
    """

    STATE_NAME = "emulation_demo_device"
    STATE_VERSION = "0.1.0"

    def __init__(self, args):
        super(DemoEmulatedDevice, self).__init__(args)

        peripheral = DemoEmulatedTile(11, device=self)
        peripheral.declare_config_variable('test 1', 0x8000, 'uint32_t')
        peripheral.declare_config_variable('test 2', 0x8001, 'uint8_t[16]')

        self.add_tile(11, peripheral)
