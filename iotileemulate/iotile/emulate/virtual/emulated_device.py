"""Base class for virtual devices designed to emulate physical devices."""

import logging
from iotile.core.exceptions import DataError
from iotile.core.utilities import SharedLoop
from iotile.core.hw.virtual import StandardVirtualDevice, pack_rpc_payload, unpack_rpc_payload
from iotile.core.hw.exceptions import AsynchronousRPCResponse, BusyRPCResponse
from .emulation_mixin import EmulationMixin
from .state_log import EmulationStateLog
from ..constants.rpcs import RPCDeclaration
from ..internal import EmulationLoop
from ..utilities import format_rpc


#pylint:disable=abstract-method;This is an abstract base class
class EmulatedDevice(EmulationMixin, StandardVirtualDevice):
    """Base class for virtual devices designed to emulate physical devices.

    This class adds additional state and test scenario loading functionality
    as well as tracing of state changes on the emulated device for comparison
    and verification purposes.

    Since all IOTile devices have a single TileBus interface that serializes
    RPCs between tiles so that only one runs at a time, this class spawns a
    single background rpc to work through the queue of RPCs that should be
    sent, sending them one at a time.  The rpc dispatch queue is started when
    start() is called and stopped synchronously when stop() is called.

    Args:
        iotile_id (int): A 32-bit integer that specifies the globally unique ID
            for this IOTile device.
        loop (BackgroundEventLoop): The loop to use to run this device's simulation.
    """

    __NO_EXTENSION__ = True

    def __init__(self, iotile_id, *, loop=SharedLoop):
        self.state_history = EmulationStateLog()

        StandardVirtualDevice.__init__(self, iotile_id)
        EmulationMixin.__init__(self, None, self.state_history)

        self._logger = logging.getLogger(__name__)
        self.emulator = EmulationLoop(self._dispatch_rpc, loop=loop)

    async def _dispatch_rpc(self, address, rpc_id, arg_payload):
        """Background work queue handler to dispatch RPCs."""

        if self.emulator.is_tile_busy(address):
            self._track_change('device.rpc_busy_response', (address, rpc_id, arg_payload, None, None), formatter=format_rpc)
            raise BusyRPCResponse()

        try:
            # Send the RPC immediately and wait for the response
            resp = await super(EmulatedDevice, self).async_rpc(address, rpc_id, arg_payload)
            self._track_change('device.rpc_sent', (address, rpc_id, arg_payload, resp, None), formatter=format_rpc)

            return resp
        except AsynchronousRPCResponse:
            self._track_change('device.rpc_started', (address, rpc_id, arg_payload, None, None), formatter=format_rpc)
            raise
        except Exception as exc:
            self._track_change('device.rpc_exception', (address, rpc_id, arg_payload, None, exc), formatter=format_rpc)
            raise

    def finish_async_rpc(self, address, rpc_id, response):
        """Finish a previous asynchronous RPC.

        This method should be called by a peripheral tile that previously
        had an RPC called on it and chose to response asynchronously by
        raising ``AsynchronousRPCResponse`` in the RPC handler itself.

        The response passed to this function will be returned to the caller
        as if the RPC had returned it immediately.

        The rpc response will be sent in the RPC thread.  By default this
        method will block until the response is finished.  If you don't
        want to block, you can pass sync=False

        Args:
            address (int): The tile address the RPC was called on.
            rpc_id (int): The ID of the RPC that was called.
            response (bytes): The bytes that should be returned to
                the caller of the RPC.
        """

        try:
            self.emulator.finish_async_rpc(address, rpc_id, response)
            self._track_change('device.rpc_finished', (address, rpc_id, None, response, None), formatter=format_rpc)
        except Exception as exc:
            self._track_change('device.rpc_exception', (address, rpc_id, None, response, exc), formatter=format_rpc)
            raise

    def start(self, channel=None):
        """Start this emulated device.

        This triggers the controller to call start on all peripheral tiles in
        the device to make sure they start after the controller does and then
        it waits on each one to make sure they have finished initializing
        before returning.

        Args:
            channel (AbstractAsyncDeviceChannel): A channel to allow pushing
                events to the client asynchronously.
        """

        super(EmulatedDevice, self).start(channel)
        self.emulator.start()

    def stop(self):
        """Stop running this virtual device including any worker threads."""

        self.emulator.stop()
        super(EmulatedDevice, self).stop()

    def dump_state(self):
        """Dump the current state of this emulated object as a dictionary.

        Returns:
            dict: The current state of the object that could be passed to load_state.
        """

        state = {}

        state['tile_states'] = {}

        for address, tile in self._tiles.items():
            state['tile_states'][address] = tile.dump_state()

        return state

    async def async_rpc(self, address, rpc_id, payload=b""):
        """Call an RPC by its address and ID.

        This will send the RPC to the background rpc dispatch thread and
        synchronously wait for the response.

        Args:
            address (int): The address of the mock tile this RPC is for
            rpc_id (int): The number of the RPC
            payload (bytes): A byte string of payload parameters up to 20 bytes

        Returns:
            bytes: the response payload from the RPC
        """

        return await self.emulator.call_rpc_internal(address, rpc_id, payload)

    def synchronize_task(self, func, *args, **kwargs):
        """Run callable in the rpc thread and wait for it to finish.

        The callable ``func`` will be passed into the EmulationLoop and run
        there.  This method will block until ``func`` is finished and
        return/raise whatever that callable returns/raises.

        This method is mainly useful for performing an activity that needs to
        be synchronized with the rpc thread for safety reasons.

        If this method is called from the rpc thread itself, it will just
        run the task and return its result.

        Args:
            func (callable): A method with signature callable(*args, **kwargs),
                that will be called with the optional *args and **kwargs passed
                to this method.
            *args: Arguments that will be passed to callable.
            **kwargs: Keyword arguments that will be passed to callable.

        Returns:
            object: Whatever callable returns after it runs.
        """

        if self.emulator.on_emulation_thread():
            return func(*args, **kwargs)

        async def _runner():
            return func(*args, **kwargs)

        return self.emulator.run_task_external(_runner())

    def wait_idle(self):
        """Wait until the emulated device is idle.

        An idle device is one where there are no tasks pending on the
        emulation thread. This is different from wait_deferred_rpcs() a given
        rpc that was scheduled before your call to wait_deferred_rpcs() could
        have scheduled an rpc to run after your call.

        This method gives you a deterministic way to wait until there is no
        more activity on the device.  This is particularly useful for
        deterministic testing because you can start an action and know
        precisely when all potential chain reactions have stopped.

        The behavior of this function depends on whether it is called within
        or outside of the emulation loop.  If it is called within the emulation
        loop then it returns an awaitable object so the correct usage is:
        ``await wait_idle()``.

        If it is called outside of the event loop it blocks the calling thread
        synchronously until the device is idle and returns None.

        This method is safe to call either inside or outside of the emulation
        loop.  However, if you are calling it inside of the emulation loop,
        you need to make sure you are not creating a deadlock by waiting for
        an idle condition inside of a handler function that must finish before
        the device can be idle.  It is not possible to deadlock with this
        function if called from outside of the event loop.
        """

        return self.emulator.wait_idle()

    def restore_state(self, state):
        """Restore the current state of this emulated device.

        Args:
            state (dict): A previously dumped state produced by dump_state.
        """

        tile_states = state.get('tile_states', {})

        for address, tile_state in tile_states.items():
            address = int(address)
            tile = self._tiles.get(address)
            if tile is None:
                raise DataError("Invalid dumped state, tile does not exist at address %d" % address, address=address)

            tile.restore_state(tile_state)

    def load_metascenario(self, scenario_list):
        """Load one or more scenarios from a list.

        Each entry in scenario_list should be a dict containing at least a
        name key and an optional tile key and args key.  If tile is present
        and its value is not None, the scenario specified will be loaded into
        the given tile only.  Otherwise it will be loaded into the entire
        device.

        If the args key is specified is will be passed as keyword arguments
        to load_scenario.

        Args:
            scenario_list (list): A list of dicts for each scenario that should
                be loaded.
        """

        for scenario in scenario_list:
            name = scenario.get('name')
            if name is None:
                raise DataError("Scenario in scenario list is missing a name parameter", scenario=scenario)

            tile_address = scenario.get('tile')
            args = scenario.get('args', {})

            dest = self
            if tile_address is not None:
                dest = self._tiles.get(tile_address)

                if dest is None:
                    raise DataError("Attempted to load a scenario into a tile address that does not exist", address=tile_address, valid_addresses=list(self._tiles))

            dest.load_scenario(name, **args)
