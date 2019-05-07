"""Main class where all emulation takes place."""

import sys
import logging
import asyncio

from iotile.core.utilities import SharedLoop
from iotile.core.exceptions import ArgumentError, InternalError, TimeoutExpiredError
from iotile.core.hw.virtual import unpack_rpc_payload, pack_rpc_payload

from .response import CrossThreadResponse, AwaitableResponse
from .rpc_queue import RPCQueue
from ..constants.rpcs import RPCDeclaration
from ..common import RPCRuntimeError

if sys.version_info < (3, 5):
    raise ImportError("EmulationLoop is only supported on python 3.5 and above")


class EmulationLoop:
    """A background thread that runs an event loop emulating a device.

    The loop is started when start() is called and cleanly stopped when stop()
    is called.  Coroutines can be added to the event loop that are tracked and
    can be stopped to simulate a device reset.

    The loop is executed on a background thread so that you can control the
    loop from the main thread.  Since this loop is designed for simulating an
    IOTile device as part of a larger emulator, it naturally has support for
    invoking RPCs inside the loop.  You must provide a handler function that
    actually dispatches the rpc.  Your handler will always be run inside the
    event loop.  There are two ways to invoke the rpcs, `await_rpc` and
    `call_rpc_external`.

    `await_rpc` must always be called from a coroutine inside the event loop
    and returns an awaitable. `call_rpc_external` must never be called from
    the event loop and is designed to be used by external callers to inject
    RPCs into the emulation.

    Unlike a normal asyncio.EventLoop, which does not have an externally
    visible concept of being idle, there is a method `wait_idle()` on
    EmulationLoop that will block until the emulator is idle.  Idleness is
    defined as when all internal workqueues inside the emulated device are
    empty.  This includes having no pending RPCs as a base condition, but any
    tile can also register work queues that contain background work and must
    be empty for the emulator to be considered idle.

    The ``wait_idle()`` method is the primary way that external users are able
    to synchronously interact with the EmulationLoop.  They can apply a
    stimulus like sending and RPC and then call wait_idle() to wait until all
    of the ripples of the RPC have settled down.  This allows for writing
    simple synchronous code that interacts with the EmulationLoop externally.

    Args:
        rpc_handler (callable): The method that actually dispatches each RPC.
            This method will always be invoked inside of the event loop.
        loop (BackgroundEventLoop): The underlying event loop to use.
    """

    def __init__(self, rpc_handler, loop=SharedLoop):
        self._loop = loop
        self._thread = None
        self._started = False
        self._tasks = {}
        self._rpc_queue = RPCQueue(self._loop.get_loop(), rpc_handler)
        self._work_queues = set([self._rpc_queue])
        self._events = set()
        self._logger = logging.getLogger(__name__)

    def create_event(self, register=False):
        """Create an asyncio.Event inside the emulation loop.

        This method exists as a convenience to create an Event object that is
        associated with the correct EventLoop().  If you pass register=True,
        then the event will be registered as an event that must be set for the
        EmulationLoop to be considered idle.  This means that whenever
        wait_idle() is called, it will block until this event is set.

        Examples of when you may want this behavior is when the event is
        signaling whether a tile has completed restarting itself.  The reset()
        rpc cannot block until the tile has initialized since it may need to
        send its own rpcs as part of the initialization process.  However, we
        want to retain the behavior that once the reset() rpc returns the tile
        has been completely reset.

        The cleanest way of achieving this is to have the tile set its
        self.initialized Event when it has finished rebooting and register
        that event so that wait_idle() nicely blocks until the reset process
        is complete.

        Args:
            register (bool): Whether to register the event so that wait_idle
                blocks until it is set.

        Returns:
            asyncio.Event: The Event object.
        """

        event = self._loop.create_event()
        if register:
            self._events.add(event)

        return event

    def create_queue(self, register=False):
        """Create a new work queue and optionally register it.

        This will make sure the queue is attached to the correct event loop.
        You can optionally choose to automatically register it so that
        wait_idle() will block until the queue is empty.

        Args:
            register (bool): Whether to call register_workqueue() automatically.

        Returns:
            asyncio.Queue: The newly created queue.
        """

        queue = self._loop.create_queue()
        if register:
            self._work_queues.add(queue)

        return queue

    def get_current_rpc(self):
        """Get the currently running RPC for asynchronous responses.

        Returns the address and rpc_id of the RPC that is currently being
        dispatched. This information can be saved and passed later to
        finish_async_rpc() to send a response to an asynchronous rpc.

        Returns:
            (address, rpc_id): A tuple with the currently running RPC.
        """

        self.verify_calling_thread(True, "Only the emulation thread is allowed to inspect the current rpc")
        return self._rpc_queue.get_current_rpc()

    def finish_async_rpc(self, address, rpc_id, *response):
        """Finish a previous asynchronous RPC.

        This method should be called by a peripheral tile that previously
        had an RPC called on it and chose to response asynchronously by
        raising ``AsynchronousRPCResponse`` in the RPC handler itself.

        The response passed to this function will be returned to the caller
        as if the RPC had returned it immediately.

        This method must only ever be called from a coroutine inside the
        emulation loop that is handling background work on behalf of a tile.

        Args:
            address (int): The tile address the RPC was called on.
            rpc_id (int): The ID of the RPC that was called.
            *response: The response that should be returned to the caller.

                This can either be a single bytes or bytearray object or a
                str object containing the format code followed by the required
                number of python objects that will then be packed using
                pack_rpc_payload(format, args).

                If you pass no additional response arguments then an
                empty response will be given.
        """

        self.verify_calling_thread(True, "All asynchronous rpcs must be finished from within the emulation loop")

        if len(response) == 0:
            response_bytes = b''
        elif len(response) == 1:
            response_bytes = response[0]

            if not isinstance(response_bytes, (bytes, bytearray)):
                raise ArgumentError("When passing a binary response to finish_async_rpc, you must "
                                    "pass a bytes or bytearray object", response=response_bytes)
        else:
            resp_format = response[0]
            resp_args = response[1:]

            if not isinstance(resp_format, str):
                raise ArgumentError("When passing a formatted response to finish_async_rpc, you must "
                                    "pass a str object with the format code as the first parameter after "
                                    "the rpc id.", resp_format=resp_format, additional_args=resp_args)

            response_bytes = pack_rpc_payload(resp_format, resp_args)

        self._rpc_queue.finish_async_rpc(address, rpc_id, response_bytes)

    def start(self):
        """Start the background emulation loop."""

        if self._started is True:
            raise ArgumentError("EmulationLoop.start() called multiple times")

        self._loop.start()
        self._rpc_queue.start()
        self._started = True

    def stop(self):
        """Stop the background emulation loop."""

        if self._started is False:
            raise ArgumentError("EmulationLoop.stop() called without calling start()")

        self.verify_calling_thread(False, "Cannot call EmulationLoop.stop() from inside the event loop")
        self._loop.run_coroutine(self._clean_shutdown())

    def wait_idle(self, timeout=1.0):
        """Wait until the rpc queue is empty.

        This method may be called either from within the event loop or from
        outside of it.  If it is called outside of the event loop it will
        block the calling thread until the rpc queue is temporarily empty.

        If it is called from within the event loop it will return an awaitable
        object that can be used to wait for the same condition.

        The awaitable object will already have a timeout if the timeout
        parameter is passed.

        Args:
            timeout (float): The maximum number of seconds to wait.
        """

        async def _awaiter():
            background_work = {x.join() for x in self._work_queues}
            for event in self._events:
                if not event.is_set():
                    background_work.add(event.wait())

            _done, pending = await asyncio.wait(background_work, timeout=timeout)
            if len(pending) > 0:
                raise TimeoutExpiredError("Timeout waiting for event loop to become idle", pending=pending)

        if self.on_emulation_thread():
            return asyncio.wait_for(_awaiter(), timeout=timeout)

        self.run_task_external(_awaiter())
        return None

    def run_task_external(self, coroutine):
        """Inject a task into the emulation loop and wait for it to finish.

        The coroutine parameter is run as a Task inside the EmulationLoop
        until it completes and the return value (or any raised Exception) is
        pased back into the caller's thread.

        Args:
            coroutine (coroutine): The task to inject into the event loop.

        Returns:
            object: Whatever the coroutine returned.
        """

        self.verify_calling_thread(False, 'run_task_external must not be called from the emulation thread')
        return self._loop.run_coroutine(coroutine)

    def call_rpc_external(self, address, rpc_id, arg_payload, timeout=10.0):
        """Call an RPC from outside of the event loop and block until it finishes.

        This is the main method by which a caller outside of the EmulationLoop
        can inject an RPC into the EmulationLoop and wait for it to complete.
        This method is synchronous so it blocks until the RPC completes or the
        timeout expires.

        Args:
            address (int): The address of the mock tile this RPC is for
            rpc_id (int): The number of the RPC
            payload (bytes): A byte string of payload parameters up to 20 bytes
            timeout (float): The maximum time to wait for the RPC to finish.

        Returns:
            bytes: The response payload from the RPC
        """

        self.verify_calling_thread(False, "call_rpc_external is for use **outside** of the event loop")

        response = CrossThreadResponse()

        self._loop.get_loop().call_soon_threadsafe(self._rpc_queue.put_rpc, address, rpc_id, arg_payload, response)

        try:
            return response.wait(timeout)
        except RPCRuntimeError as err:
            return err.binary_error

    async def call_rpc_internal(self, address, rpc_id, arg_payload, timeout=10.0):
        """Call an RPC from inside of the event loop and yield until it finishes.

        This is the main method by which a caller inside of the EmulationLoop
        can inject an RPC into the EmulationLoop and wait for it to complete.

        Args:
            address (int): The address of the mock tile this RPC is for
            rpc_id (int): The number of the RPC
            payload (bytes): A byte string of payload parameters up to 20 bytes
            timeout (float): The maximum time to wait for the RPC to finish.

        Returns:
            bytes: The response payload from the RPC
        """

        self.verify_calling_thread(True, "call_rpc_internal is for use **inside** of the event loop")

        response = AwaitableResponse()
        self._rpc_queue.put_rpc(address, rpc_id, arg_payload, response)

        try:
            resp_payload = await response.wait(timeout)
        except RPCRuntimeError as err:
            resp_payload = err.binary_error

        return resp_payload

    async def await_rpc(self, address, rpc_id, *args, **kwargs):
        """Send an RPC from inside the EmulationLoop.

        This is the primary method by which tasks running inside the
        EmulationLoop dispatch RPCs.  The RPC is added to the queue of waiting
        RPCs to be drained by the RPC dispatch task and this coroutine will
        block until it finishes.

        **This method must only be called from inside the EmulationLoop**

        Args:
            address (int): The address of the tile that has the RPC.
            rpc_id (int): The 16-bit id of the rpc we want to call
            *args: Any required arguments for the RPC as python objects.
            **kwargs: Only two keyword arguments are supported:
                - arg_format: A format specifier for the argument list
                - result_format: A format specifier for the result

        Returns:
            list: A list of the decoded response members from the RPC.
        """

        self.verify_calling_thread(True, "await_rpc must be called from **inside** the event loop")

        if isinstance(rpc_id, RPCDeclaration):
            arg_format = rpc_id.arg_format
            resp_format = rpc_id.resp_format
            rpc_id = rpc_id.rpc_id
        else:
            arg_format = kwargs.get('arg_format', None)
            resp_format = kwargs.get('resp_format', None)

        arg_payload = b''

        if arg_format is not None:
            arg_payload = pack_rpc_payload(arg_format, args)

        self._logger.debug("Sending rpc to %d:%04X, payload=%s", address, rpc_id, args)

        response = AwaitableResponse()
        self._rpc_queue.put_rpc(address, rpc_id, arg_payload, response)

        try:
            resp_payload = await response.wait(1.0)
        except RPCRuntimeError as err:
            resp_payload = err.binary_error

        if resp_format is None:
            return []

        resp = unpack_rpc_payload(resp_format, resp_payload)
        return resp

    def verify_calling_thread(self, should_be_emulation, message=None):
        """Verify if the calling thread is or is not the emulation thread.

        This method can be called to make sure that an action is being taken
        in the appropriate context such as not blocking the event loop thread
        or modifying an emulate state outside of the event loop thread.

        If the verification fails an InternalError exception is raised,
        allowing this method to be used to protect other methods from being
        called in a context that could deadlock or cause race conditions.

        Args:
            should_be_emulation (bool): True if this call should be taking place
                on the emulation, thread, False if it must not take place on
                the emulation thread.
            message (str): Optional message to include when raising the exception.
                Otherwise a generic message is used.

        Raises:
            InternalError: When called from the wrong thread.
        """

        if should_be_emulation == self.on_emulation_thread():
            return

        if message is None:
            message = "Operation performed on invalid thread"

        raise InternalError(message)

    def add_task(self, tile_address, coroutine):
        """Add a task into the event loop.

        This is the main entry point for registering background tasks that are
        associated with a tile. The tasks are added to the EmulationLoop and
        the tile they are a part of is recorded.  When the tile is reset, all
        of its background tasks are canceled as part of the reset process.

        If you have a task that should not be associated with any tile, you
        may pass `None` for tile_address and the task will not be cancelled
        when any tile is reset.

        Args:
            tile_address (int): The address of the tile running
                the task.
            coroutine (coroutine): A coroutine that will be added
                to the event loop.
        """

        self._loop.get_loop().call_soon_threadsafe(self._add_task, tile_address, coroutine)

    def is_tile_busy(self, address):
        """Check that tile has no pending rpcs

        Args:
            address (int): The address of the time

        Returns:
            bool: True if there is a rpc for the tile already in the queue
        """
        return self._rpc_queue.is_pending_rpc(address)

    def on_emulation_thread(self):
        """Returns whether we are running on the emulation thread.

        Returns:
            bool: True if we are on the emulation thread, else False.
        """

        return self._loop.inside_loop()

    async def stop_tasks(self, address):
        """Clear all tasks pertaining to a tile.

        This coroutine will synchronously cancel all running tasks that were
        attached to the given tile and wait for them to stop before returning.

        Args:
            address (int): The address of the tile we should stop.
        """

        tasks = self._tasks.get(address, [])
        for task in tasks:
            task.cancel()

        asyncio.gather(*tasks, return_exceptions=True)
        self._tasks[address] = []

    async def _clean_shutdown(self):
        """Cleanly shutdown the emulation loop."""

        # Cleanly stop any other outstanding tasks not associated with tiles
        remaining_tasks = []
        for task in self._tasks.get(None, []):
            self._logger.debug("Cancelling task at shutdown %s", task)
            task.cancel()

            remaining_tasks.append(task)

        asyncio.gather(*remaining_tasks, return_exceptions=True)

        if len(remaining_tasks) > 0:
            del self._tasks[None]

        # Shutdown tasks associated with each tile
        remaining_tasks = []

        for address in sorted(self._tasks, reverse=True):
            if address is None:
                continue

            self._logger.debug("Shutting down tasks for tile at %d", address)
            for task in self._tasks.get(address, []):
                task.cancel()
                remaining_tasks.append(task)

        asyncio.gather(*remaining_tasks, return_exceptions=True)

        await self._rpc_queue.stop()

    def _add_task(self, tile_address, coroutine):
        """Add a task from within the event loop.

        All tasks are associated with a tile so that they can be cleanly
        stopped when that tile is reset.
        """

        self.verify_calling_thread(True, "_add_task is not thread safe")

        if tile_address not in self._tasks:
            self._tasks[tile_address] = []

        task = self._loop.get_loop().create_task(coroutine)
        self._tasks[tile_address].append(task)
