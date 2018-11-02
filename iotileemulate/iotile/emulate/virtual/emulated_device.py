"""Base class for virtual devices designed to emulate physical devices."""

from __future__ import unicode_literals, absolute_import, print_function
from future.utils import viewitems
from iotile.core.exceptions import DataError
from iotile.core.hw.virtual import VirtualIOTileDevice
from iotile.core.hw.virtual.common_types import pack_rpc_payload, unpack_rpc_payload
from .emulation_mixin import EmulationMixin
from .state_log import EmulationStateLog
from ..constants.rpcs import RPCDeclaration


#pylint:disable=abstract-method;This is an abstract base class
class EmulatedDevice(EmulationMixin, VirtualIOTileDevice):
    """Base class for virtual devices designed to emulate physical devices.

    This class adds additional state and test scenario loading functionality
    as well as tracing of state changes on the emulated device for comparison
    and verification purposes.

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

        self._deferred_rpcs = []

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
        with each other.  It may only be called from the main virtual device
        thread where start() was called from.

        **Background workers may not call this method since it is unsynchronized.**

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

        resp_payload = self.call_rpc(address, rpc_id, arg_payload)
        if resp_format is None:
            return []

        resp = unpack_rpc_payload(resp_format, resp_payload)
        return resp

    def deferred_rpc(self, address, rpc_id, *args, **kwargs):
        """Queue an RPC to send later.

        These RPCs will be sent deterministically whenever send_deferred_rpcs()
        is called.

        **Background workers may not call this method since it is unsynchronized.**

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

        callback = kwargs.get('callback')
        if 'callback' in kwargs:
            del kwargs['callback']

        rpc_args = (address, rpc_id, args, kwargs, callback)
        self._deferred_rpcs.append(rpc_args)

    def send_deferred_rpcs(self):
        """Send all deferred rpcs currently in the queue."""

        for address, rpc_id, args, kwargs, callback in self._deferred_rpcs:
            resp = self.rpc(address, rpc_id, *args, **kwargs)

            if callback is not None:
                callback(resp)

        self._deferred_rpcs = []

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
