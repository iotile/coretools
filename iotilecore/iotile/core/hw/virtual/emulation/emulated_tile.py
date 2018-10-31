"""Base class for virtual tiles designed to emulate physical tiles."""

from __future__ import unicode_literals, absolute_import, print_function

import struct
import base64
from future.utils import viewitems
from iotile.core.exceptions import ArgumentError
from ..virtualtile import VirtualTile
from ..common_types import tile_rpc
from .emulated_device import EmulatedDevice
from .emulation_mixin import EmulationMixin


class ConfigDescriptor(object):
    """Helper class for declaring a configuration variable.

    FIXME: Support binary serialization of default values.
    """

    def __init__(self, config_id, type_name, default=None, name=None):
        self.config_id = config_id
        self.total_size, self.unit_size, self.base_type, self.variable = parse_size_name(type_name)
        self.max_units = self.total_size // self.unit_size
        self.type_name = type_name
        self.default_value = default
        self.current_value = bytearray()

        if name is None:
            name = "Unnamed variable 0x%X" % config_id

        self.name = name

    def update_value(self, offset, value):
        """Update the binary value currently stored for this config value.

        Returns:
            int: An opaque error code that can be returned from a set_config rpc
        """

        if offset + len(value) > self.total_size:
            return 3

        if len(self.current_value) < offset:
            self.current_value += bytearray(offset - len(self.current_value))
        if len(self.current_value) > offset:
            self.current_value = self.current_value[:offset]

        self.current_value += bytearray(value)
        return 0


#pylint:disable=abstract-method;This is an abstract base class
class EmulatedTile(EmulationMixin, VirtualTile):
    """Base class for virtual tiles designed to emulate physical tiles.

    This class adds additional state and test scenario loading functionality
    as well as tracing of state changes on the emulated device for comparison
    and verification purposes.

    There is a small set of behavior that all tiles must implement which is
    implemented in this class including a base set of RPCs for setting
    config variables and getting the tile's name (inherited from VirtualTile).

    FIXME: capture the value of the config variable on reset (for controllers) or
           on receipt of the start_application rpc for peripheral tiles.

    Args:
        address (int): The address of this tile in the VirtualIOTIleDevice
            that contains it
        name (str): The 6 character name that should be returned when this
            tile is asked for its status to allow matching it with a proxy
            object.
        device (TileBasedVirtualDevice): Device on which this tile is running.
            This parameter is not optional on EmulatedTiles.
    """

    def __init__(self, address, name, device):
        if not isinstance(device, EmulatedDevice):
            raise ArgumentError("You can only add an EmulatedTile to an EmulatedDevice", device=device)

        VirtualTile.__init__(self, address, name, device)
        EmulationMixin.__init__(self, address, device.state_history)

        self._config_variables = {}

    def declare_config_variable(self, name, config_id, type_name, default_value=None):
        """Declare a config variable that this emulated tile accepts.

        Args:
            name (str): A user friendly name for this config variable so that it can
                be printed nicely.
            config_id (int): A 16-bit integer id number to identify the config variable.
            type_name (str): An encoded type name that will be parsed by parse_size_name()
            default_value (object): The default value if there is one.  This should be a
                python object that will be converted to binary according to the rules for
                the config variable type specified in type_name.
        """

        config = ConfigDescriptor(config_id, type_name, default_value, name=name)
        self._config_variables[config_id] = config

    def dump_state(self):
        """Dump the current state of this emulated tile as a dictionary.

        This function just dumps the status of the config variables.  It is designed to
        be called in a chained fashion to serialize the complete state of a tile subclass.

        Returns:
            dict: The current state of the object that could be passed to load_state.
        """

        return {
            "config_variables": {x: base64.b64encode(y) for x, y in viewitems(self._config_variables)}
        }

    def restore_state(self, state):
        """Restore the current state of this emulated object.

        Args:
            state (dict): A previously dumped state produced by dump_state.
        """

        config_vars = state.get('config_variables', {})

        for str_name, str_value in viewitems(config_vars):
            name = int(str_name)
            value = base64.b64decode(str_value)

            if name in self._config_variables:
                self._config_variables[name].current_value = value

    def handle_reset(self):
        """Hook to perform any required reset actions."""

        pass

    @tile_rpc(1, "")
    def reset(self):
        """Reset this tile."""

        self.handle_reset()

    @tile_rpc(10, "H", "H9H")
    def list_config_variables(self, offset):
        """List defined config variables up to 9 at a time."""

        names = sorted(self._config_variables)
        names = names[offset:offset + 9]
        count = len(names)

        if len(names) < 9:
            names += [0]*(9 - count)

        return [count] + names

    @tile_rpc(11, "H", "HHLHH")
    def describe_config_variable(self, config_id):
        """Describe the config variable by its id."""

        config = self._config_variables.get(config_id)
        if config is None:
            return [6, 0, 0, 0, 0]

        packed_size = config.total_size
        packed_size |= int(config.variable) << 15

        return [0, 0, 0, config_id, packed_size]

    @tile_rpc(12, "HHV", "H")
    def set_config_value(self, config_id, offset, value):
        """Set a chunk of the current config value's value."""

        # FIXME: disallow config value setting once app_started has been set.
        config = self._config_variables.get(config_id)
        if config is None:
            return [6]

        error = config.update_value(offset, value)
        return [error]

    @tile_rpc(13, "HH", "V")
    def get_config_value(self, config_id, offset):
        """Get a chunk of a config variable's value."""

        config = self._config_variables.get(config_id)
        if config is None:
            return [b""]

        return [config.current_value[offset:offset + 20]]


TYPE_CODES = {'uint8_t': 'B', 'char': 'B', 'int8_t': 'b', 'uint16_t': 'H', 'int16_t': 'h', 'uint32_t': 'L', 'int32_t': 'l'}


def parse_size_name(type_name):
    """Return the size and whether it is variable for a given common name."""

    if ' ' in type_name:
        raise ArgumentError("There should not be a space in config variable type specifier", specifier=type_name)

    variable = False
    count = 1
    base_type = type_name

    if type_name[-1] == ']':
        variable = True
        start_index = type_name.find('[')
        if start_index == -1:
            raise ArgumentError("Could not find matching [ for ] character", specifier=type_name)

        count = int(type_name[start_index+1:-1], 0)
        base_type = type_name[:start_index]

    matched_type = TYPE_CODES.get(base_type)
    if matched_type is None:
        raise ArgumentError("Could not find base type name", base_type=base_type, type_string=type_name)

    base_size = struct.calcsize("<%s" % matched_type)
    total_size = base_size*count

    return total_size, base_size, matched_type, variable
