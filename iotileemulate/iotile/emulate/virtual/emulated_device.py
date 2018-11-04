"""Base class for virtual devices designed to emulate physical devices."""

from __future__ import unicode_literals, absolute_import, print_function
import logging
import threading
import sys
from collections import namedtuple
from queue import Queue
from future.utils import viewitems
from iotile.core.exceptions import DataError
from iotile.core.hw.virtual import VirtualIOTileDevice
from iotile.core.hw.virtual.common_types import pack_rpc_payload, unpack_rpc_payload
from .emulation_mixin import EmulationMixin
from .state_log import EmulationStateLog
from ..constants.rpcs import RPCDeclaration
from ..constants import rpc_name
from ..utilities import format_rpc

# Kill signal to stop our background RPC worker thread
_STOP_RPC_WORKER = object()

# Signal to synchronously wait for all previous rpcs to be dispatched
_WAIT_FOR_RPCS = namedtuple('_WAIT_FOR_RPCS', ['callback'])  #pylint:disable=invalid-name;


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

    def __init__(self, iotile_id, name):
        self.state_history = EmulationStateLog()

        VirtualIOTileDevice.__init__(self, iotile_id, name)
        EmulationMixin.__init__(self, None, self.state_history)

        self._logger = logging.getLogger(__name__)
        self._rpc_queue = Queue()
        self._rpc_thread = threading.Thread(target=self._rpc_dispatch_loop)

    def _rpc_dispatch_loop(self):
        """Background thread routine to dispatch RPCs."""

        while True:
            try:
                action = self._rpc_queue.get()

                # Handle special actions that are not RPCs
                if action is _STOP_RPC_WORKER:
                    return
                elif isinstance(action, _WAIT_FOR_RPCS):
                    action.callback()
                    continue

                # Otherwise, we are supposed to send an RPC
                address, rpc_id, arg_payload, callback = action

                try:
                    exc_status = None
                    exc_info = None
                    resp = None

                    # Send the RPC immediately and wait for the respones
                    resp = super(EmulatedDevice, self).call_rpc(address, rpc_id, arg_payload)
                except:
                    exc_info = sys.exc_info()
                    exc_status = exc_info[1]
                finally:
                    self._track_change('device.rpc_sent', (address, rpc_id, arg_payload, resp, exc_status), formatter=format_rpc)

                if callback is not None:
                    callback(exc_info, resp)
            except:
                self._logger.exception("Error dispatching %s to tile %d", rpc_name(rpc_id), address)


    def start(self, channel=None):
        """Start this emulated device.

        This triggers the controller to call start on all peripheral tiles in the device to make sure
        they start after the controller does and then it waits on each one to make sure they have
        finished initializing before returning.

        Args:
            channel (IOTilePushChannel): the channel with a stream and trace
                routine for streaming and tracing data through a VirtualInterface
        """

        super(EmulatedDevice, self).start(channel)
        self._rpc_thread.start()

    def stop(self):
        """Stop running this virtual device including any worker threads."""

        if self._rpc_thread.is_alive():
            self._rpc_queue.put(_STOP_RPC_WORKER)
            self._rpc_thread.join()

        super(EmulatedDevice, self).stop()

    def dump_state(self):
        """Dump the current state of this emulated object as a dictionary.

        Returns:
            dict: The current state of the object that could be passed to load_state.
        """

        state = {}

        state['tile_states'] = {}

        for address, tile in viewitems(self._tiles):
            state['tile_states'][address] = tile.dump_state()

        return state

    def rpc(self, address, rpc_id, *args, **kwargs):
        """Immediately dispatch an RPC inside this EmulatedDevice.

        This function is meant to be used for testing purposes as well as by
        tiles inside a complex EmulatedDevice subclass that need to communicate
        with each other.  It should only be called from the main virtual device
        thread where start() was called from.

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

        done = threading.Event()
        data = [None, None]

        def _callback(status_error, resp_payload):
            data[0] = status_error
            data[1] = resp_payload
            done.set()

        self._rpc_queue.put((address, rpc_id, payload, _callback))

        done.wait(timeout=10)
        status_error, resp_payload = data
        if status_error is not None:
            raise status_error[0], status_error[1], status_error[2]  #pylint:disable=unsubscriptable-object;The call to done.wait() ensures this is okay.

        return resp_payload

    def deferred_rpc(self, address, rpc_id, *args, **kwargs):
        """Queue an RPC to send later.

        When this RPC is called, the result of calling it will be available to
        the provided callback function if passed as keyword.  If no 'callback'
        keyword is provided then the rpc will be called and its result will be
        discarded.

        Args:
            address (int): The address of the tile that has the RPC.
            rpc_id (int): The 16-bit id of the rpc we want to call
            *args: Any required arguments for the RPC as python objects.
            **kwargs: Only three keyword arguments are supported:
                - arg_format: A format specifier for the argument list
                - result_format: A format specifier for the result
                - callback: optional callable that is called with the response from the RPC.
                  This can be used to queue state changes that should happen when the RPC
                  finishes.
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

        callback = kwargs.get('callback')
        if 'callback' in kwargs:
            del kwargs['callback']

        def _callback(_exc_info, resp_payload):
            if callback is not None:
                resp = unpack_rpc_payload(resp_format, resp_payload)
                callback(resp)

        rpc_args = (address, rpc_id, arg_payload, callback)
        self._rpc_queue.put(rpc_args)

    def wait_deferred_rpcs(self):
        """Wait until all RPCs queued to this point have been sent."""

        done = threading.Event()
        def _callback():
            done.set()

        self._rpc_queue.put(_WAIT_FOR_RPCS(_callback))
        done.wait(timeout=10)

    def restore_state(self, state):
        """Restore the current state of this emulated device.

        Args:
            state (dict): A previously dumped state produced by dump_state.
        """

        tile_states = state.get('tile_states', {})

        for address, tile_state in viewitems(tile_states):
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
