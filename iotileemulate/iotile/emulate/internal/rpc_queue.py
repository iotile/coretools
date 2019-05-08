"""Helper class for dispatching rpcs inside the emulation loop."""

import asyncio
import logging
import inspect
from iotile.core.exceptions import InternalError, ArgumentError
from iotile.core.hw.exceptions import AsynchronousRPCResponse

class RPCQueue:
    """Coroutine based RPC dispatcher.

    This class wraps a coroutine draining an asyncio.Queue to dispatch RPCS.
    It keeps track of RPCs that are in progress and allows joining the queue
    to wait for an idle moment when no RPCs are pending or in progress.

    This class is primarily used to simplify the implementation of
    EmulationLoop, which creates an RPCQueue and interacts with it.

    The primary mode of interaction with this class is to call:

    - put_rpc(address, rpc_id, payload, response)
    - put_task(func, args, response)

    Those methods will add work to the RPC queue, which will be performed
    asynchronously by the background dispatcher task.  When a work item is
    finished, the response object passed in will be notified with the result.

    Args:
        loop (asyncio.EventLoop): The event loop this queue should be attached
            to.
        rpc_handler (callable): The actual handler function that we should use
            to run each RPC and get the result.
    """

    def __init__(self, loop, rpc_handler):
        self._rpc_handler = rpc_handler
        self._loop = loop
        self._rpc_queue = asyncio.Queue(loop=loop)
        self._current_rpc = None
        self._rpc_task = None
        self._pending_rpcs = {}
        self._logger = logging.getLogger(__name__)

    def put_task(self, func, args, response):
        """Place a task onto the RPC queue.

        This temporary functionality will go away but it lets you run a
        task synchronously with RPC dispatch by placing it onto the
        RCP queue.

        Args:
            func (callable): The function to execute
            args (iterable): The function arguments
            response (GenericResponse): The response object to signal the
                result on.
        """

        self._rpc_queue.put_nowait((func, args, response))

    def put_rpc(self, address, rpc_id, arg_payload, response):
        """Place an RPC onto the RPC queue.

        The rpc will be dispatched asynchronously by the background dispatch
        task.  This method must be called from the event loop.  This method
        does not block.

        Args:
            address (int): The address of the tile with the RPC
            rpc_id (int): The id of the rpc you want to call
            arg_payload (bytes): The RPC payload
            respones (GenericResponse): The object to use to signal the result.
        """

        self._rpc_queue.put_nowait((address, rpc_id, arg_payload, response))

    def join(self):
        """Wait for the RPC queue to be empty.

        Returns:
            awaitable
        """

        return self._rpc_queue.join()

    def get_current_rpc(self):
        """Get the currently running RPC for asynchronous responses.

        Returns the address and rpc_id of the RPC that is currently being
        dispatched. This information can be saved and passed later to
        finish_async_rpc() to send a response to an asynchronous rpc.

        Returns:
            (address, rpc_id): A tuple with the currently running RPC.
        """

        if self._current_rpc is None:
            raise InternalError("There is no current RPC running")

        return self._current_rpc

    def finish_async_rpc(self, address, rpc_id, response):
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
            response (bytes): The bytes that should be returned to
                the caller of the RPC.
        """

        pending = self._pending_rpcs.get(address)

        if pending is None:
            raise ArgumentError("No asynchronously RPC currently in progress on tile %d" % address)

        responder = pending.get(rpc_id)
        if responder is None:
            raise ArgumentError("RPC %04X is not running asynchronous on tile %d" % (rpc_id, address))

        del pending[rpc_id]

        responder.set_result(response)
        self._rpc_queue.task_done()

    def start(self):
        """Start this task from the event loop thread."""

        self._rpc_task = self._loop.create_task(self._rpc_dispatch_task())

    def is_pending_rpc(self, address):
        """Check if there is a pending rpc on the tile

        Args:
            address (int): The address of the time

        Returns:
            bool: True if there is a rpc for the tile already in the queue
        """

        return address in self._pending_rpcs and self._pending_rpcs[address]

    async def stop(self):
        """Stop the rpc queue from inside the event loop."""

        if self._rpc_task is not None:
            self._rpc_task.cancel()

        try:
            await self._rpc_task
        except asyncio.CancelledError:
            pass

        self._rpc_task = None

    async def _rpc_dispatch_task(self):
        self._logger.debug("Starting RPC dispatch task")

        while True:
            try:
                obj = await self._rpc_queue.get()

                if len(obj) == 3:
                    address = None
                    rpc_id = None
                    func, args, response = obj
                    result = func(*args)
                else:
                    address, rpc_id, arg_payload, response = obj

                    self._current_rpc = (address, rpc_id)
                    result = self._rpc_handler(address, rpc_id, arg_payload)
                    if inspect.isawaitable(result):
                        result = await result

                    self._current_rpc = None

                response.set_result(result)
                self._rpc_queue.task_done()
            except AsynchronousRPCResponse:
                self._queue_async_rpc(address, rpc_id, response)
            except asyncio.CancelledError:
                raise
            except:  #pylint:disable=bare-except;We want to send all exceptions to the caller.
                response.capture_exception()
                self._rpc_queue.task_done()

    def _queue_async_rpc(self, address, rpc_id, response):
        if address not in self._pending_rpcs:
            self._pending_rpcs[address] = {}

        self._pending_rpcs[address][rpc_id] = response

        self._logger.debug("Queued asynchronous rpc on tile %d, rpc_id: 0x%04X", address, rpc_id)
