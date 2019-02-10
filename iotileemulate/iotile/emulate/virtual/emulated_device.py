"""Base class for virtual devices designed to emulate physical devices."""

import logging
from iotile.core.exceptions import DataError
from iotile.core.hw.virtual import VirtualIOTileDevice
from iotile.core.hw.virtual.common_types import pack_rpc_payload, unpack_rpc_payload, AsynchronousRPCResponse
from .emulation_mixin import EmulationMixin
from .state_log import EmulationStateLog
from ..constants.rpcs import RPCDeclaration
from ..internal import EmulationLoop, AwaitableResponse
from ..utilities import format_rpc


#pylint:disable=abstract-method;This is an abstract base class
class EmulatedDevice(EmulationMixin, VirtualIOTileDevice):
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
        name (string): The 6 byte name that should be returned when anyone asks
            for the controller's name of this IOTile device using an RPC
    """

    __NO_EXTENSION__ = True

    def __init__(self, iotile_id, name):
        self.state_history = EmulationStateLog()

        VirtualIOTileDevice.__init__(self, iotile_id, name)
        EmulationMixin.__init__(self, None, self.state_history)

        self._logger = logging.getLogger(__name__)
        self.emulator = EmulationLoop(self._dispatch_rpc)

    def _dispatch_rpc(self, address, rpc_id, arg_payload):
        """Background work queue handler to dispatch RPCs."""

        try:
            # Send the RPC immediately and wait for the response
            resp = super(EmulatedDevice, self).call_rpc(address, rpc_id, arg_payload)
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
            channel (IOTilePushChannel): the channel with a stream and trace
                routine for streaming and tracing data through a VirtualInterface
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

    def rpc(self, address, rpc_id, *args, **kwargs):
        """Immediately dispatch an RPC inside this EmulatedDevice.

        This function is meant to be used for testing purposes as well as by
        tiles inside a complex EmulatedDevice subclass that need to
        communicate with each other.  It should only be called from the main
        virtual device thread where start() was called from.

        **Background workers may not call this method since it may cause them to deadlock.**

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

        resp_payload = self.call_rpc(address, rpc_id, arg_payload)
        if resp_format is None:
            return []

        resp = unpack_rpc_payload(resp_format, resp_payload)
        return resp

    def call_rpc(self, address, rpc_id, payload=b""):
        """Call an RPC by its address and ID.

        This will send the RPC to the background rpc dispatch thread and
        synchronously wait for the response.

        Args:
            address (int): The address of the mock tile this RPC is for
            rpc_id (int): The number of the RPC
            payload (bytes): A byte string of payload parameters up to 20 bytes

        Returns:
            bytes: The response payload from the RPC
        """

        return self.emulator.call_rpc_external(address, rpc_id, payload)

    def trace_sync(self, data, timeout=5.0):
        """Send tracing data and wait for it to finish.

        This awaitable coroutine wraps VirtualIOTileDevice.trace() and turns
        the callback into an awaitable object.  The appropriate usage of this
        method is by calling it inside the event loop as:

        await device.trace_sync(data)

        Args:
            data (bytes): The raw data that should be traced.
            timeout (float): The maximum number of seconds to wait before
                timing out.

        Returns:
            awaitable: An awaitable object with the result.

            The result will be True if the data was sent successfully
            or False if the data could not be sent in its entirety.

            When False is returned, there is no guarantee about how much of
            the data was sent, if any, just that it was not known to be
            successfully sent.
        """

        done = AwaitableResponse()
        self.trace(data, callback=done.set_result)
        return done.wait(timeout)

    def stream_sync(self, report, timeout=120.0):
        """Send a report and wait for it to finish.

        This awaitable coroutine wraps VirtualIOTileDevice.stream() and turns
        the callback into an awaitable object.  The appropriate usage of this
        method is by calling it inside the event loop as:

        await device.stream_sync(data)

        Args:
            report (IOTileReport): The report that should be streamed.
            timeout (float): The maximum number of seconds to wait before
                timing out.

        Returns:
            awaitable: An awaitable object with the result.

            The result will be True if the data was sent successfully
            or False if the data could not be sent in its entirety.

            When False is returned, there is no guarantee about how much of
            the data was sent, if any, just that it was not known to be
            successfully sent.
        """

        done = AwaitableResponse()
        self.stream(report, callback=done.set_result)
        return done.wait(timeout)

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

        This method will block the calling thread until the _rpc_queue is
        idle.

        **Calling wait_idle from the emulation thread would deadlock and will
        raise an exception.**
        """

        self.emulator.wait_idle()

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
