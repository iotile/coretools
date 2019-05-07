"""Base class for virtual tiles designed to emulate physical tiles."""

import struct
import base64
import logging
from iotile.core.exceptions import ArgumentError, DataError
from iotile.core.hw.exceptions import TileNotFoundError
from iotile.core.hw.virtual import tile_rpc, RPCDispatcher
from .emulated_device import EmulatedDevice
from .emulation_mixin import EmulationMixin
from ..constants import rpcs, Error


class ConfigDescriptor(object):
    """Helper class for declaring a configuration variable."""

    def __init__(self, config_id, type_name, default=None, name=None, python_type=None):
        self.config_id = config_id
        self.total_size, self.unit_size, self.base_type, self.variable = parse_size_name(type_name)
        self.max_units = self.total_size // self.unit_size
        self.type_name = type_name
        self.current_value = bytearray()
        self.special_type = python_type
        self.default_value = self._convert_default_value(default)

        self._validate_python_type(python_type)

        if name is None:
            name = "Unnamed variable 0x%X" % config_id

        self.name = name

    def _validate_python_type(self, python_type):
        """Validate the possible combinations of python_type and type_name."""

        if python_type == 'bool':
            if self.variable:
                raise ArgumentError("You can only specify a bool python type on a scalar (non-array) type_name", type_name=self.type_name)

            return

        if python_type == 'string':
            if not (self.variable and self.unit_size == 1):
                raise ArgumentError("You can only pass a string python type on an array of 1-byte objects", type_name=self.type_name)

            return

        if python_type is not None:
            raise ArgumentError("You can only declare a bool or string python type.  Otherwise it must be passed as None", python_type=python_type)

    def _convert_default_value(self, default):
        """Convert the passed default value to binary.

        The default value (if passed) may be specified as either a `bytes`
        object or a python int or list of ints.  If an int or list of ints is
        passed, it is converted to binary.  Otherwise, the raw binary data is
        used.

        If you pass a bytes object with python_type as True, do not null terminate
        it, an additional null termination will be added.

        Passing a unicode string is only allowed if as_string is True and it
        will be encoded as utf-8 and null terminated for use as a default value.
        """

        if default is None:
            return None

        if isinstance(default, str):
            if self.special_type == 'string':
                return default.encode('utf-8') + b'\0'

            raise DataError("You can only pass a unicode string if you are declaring a string type config variable", default=default)

        if isinstance(default, (bytes, bytearray)):
            if self.special_type == 'string' and isinstance(default, bytes):
                default += b'\0'

            return default

        if isinstance(default, int):
            default = [default]

        format_string = "<" + (self.base_type*len(default))
        return struct.pack(format_string, *default)

    def clear(self):
        """Clear this config variable to its reset value."""

        if self.default_value is None:
            self.current_value = bytearray()
        else:
            self.current_value = bytearray(self.default_value)

    def update_value(self, offset, value):
        """Update the binary value currently stored for this config value.

        Returns:
            int: An opaque error code that can be returned from a set_config rpc
        """

        if offset + len(value) > self.total_size:
            return Error.INPUT_BUFFER_TOO_LONG

        if len(self.current_value) < offset:
            self.current_value += bytearray(offset - len(self.current_value))
        if len(self.current_value) > offset:
            self.current_value = self.current_value[:offset]

        self.current_value += bytearray(value)
        return 0

    def latch(self):
        """Convert the current value inside this config descriptor to a python object.

        The conversion proceeds by mapping the given type name to a native
        python class and performing the conversion.  You can override what
        python object is used as the destination class by passing a
        python_type parameter to __init__.

        The default mapping is:
        - char (u)int8_t, (u)int16_t, (u)int32_t: int
        - char[] (u)int8_t[], (u)int16_t[]0, u(int32_t): list of int

        If you want to parse a char[] or uint8_t[] as a python string, it
        needs to be null terminated and you should pass python_type='string'.

        If you are declaring a scalar integer type and wish it to be decoded
        as a bool, you can pass python_type='bool' to the constructor.

        All integers are decoded as little-endian.

        Returns:
            object: The corresponding python object.

            This will either be an int, list of int or string based on the
            type_name specified and the optional python_type keyword argument
            to the constructor.

        Raises:
            DataError: if the object cannot be converted to the desired type.
            ArgumentError: if an invalid python_type was specified during construction.
        """

        if len(self.current_value) == 0:
            raise DataError("There was no data in a config variable during latching", name=self.name)

        # Make sure the data ends on a unit boundary.  This would have happened automatically
        # in an actual device by the C runtime 0 padding out the storage area.
        remaining = len(self.current_value) % self.unit_size
        if remaining > 0:
            self.current_value += bytearray(remaining)

        if self.special_type == 'string':
            if self.current_value[-1] != 0:
                raise DataError("String type was specified by data did not end with a null byte", data=self.current_value, name=self.name)

            return bytes(self.current_value[:-1]).decode('utf-8')

        fmt_code = "<" + (self.base_type * (len(self.current_value) // self.unit_size))
        data = struct.unpack(fmt_code, self.current_value)

        if self.variable:
            data = list(data)
        else:
            data = data[0]

            if self.special_type == 'bool':
                data = bool(data)

        return data


#pylint:disable=abstract-method;This is an abstract base class
class EmulatedTile(EmulationMixin, RPCDispatcher):
    """Base class for virtual tiles designed to emulate physical tiles.

    This class adds additional state and test scenario loading functionality
    as well as tracing of state changes on the emulated device for comparison
    and verification purposes.

    There is a small set of behavior that all tiles must implement which is
    implemented in this class including a base set of RPCs for setting
    config variables and getting the tile's name.

    Args:
        address (int): The address of this tile in the VirtualIOTIleDevice
            that contains it
        device (TileBasedVirtualDevice): Device on which this tile is running.
            This parameter is not optional on EmulatedTiles.
    """

    __NO_EXTENSION__ = True

    hardware_type = 0
    """The hardware type is a single uint8_t that can be used to record the chip architecture used."""

    firmware_version = (1, 0, 0)
    """The version of the application firmware running on the tile."""

    executive_version = (1, 0, 0)
    """The version of the executive kernel running on the tile."""

    api_version = (3, 0)
    """The API version agreed between the application and executive kernel."""

    app_started = None
    """Default implementation of tiles does not have a separate phase before application code runs."""

    hardware_string = b'pythontile'
    """A 10 bytes identifier for the hardware that the tile is running on."""

    name = b'noname'
    """A 6-byte identifier for the application firmware running on the tile."""

    def __init__(self, address, device):
        if not isinstance(device, EmulatedDevice):
            raise ArgumentError("You can only add an EmulatedTile to an EmulatedDevice", device=device)

        RPCDispatcher.__init__(self)
        EmulationMixin.__init__(self, address, device.state_history)

        self._config_variables = {}
        self._device = device
        self._logger = logging.getLogger(__name__)
        self.address = address
        self.initialized = device.emulator.create_event(register=True)

    def declare_config_variable(self, name, config_id, type_name, default=None, convert=None):  #pylint:disable=too-many-arguments;These are all necessary with sane defaults.
        """Declare a config variable that this emulated tile accepts.

        The default value (if passed) may be specified as either a `bytes`
        object or a python int or list of ints.  If an int or list of ints is
        passed, it is converted to binary.  Otherwise, the raw binary data is
        used.

        Passing a unicode string is only allowed if as_string is True and it
        will be encoded as utf-8 and null terminated for use as a default value.

        Args:
            name (str): A user friendly name for this config variable so that it can
                be printed nicely.
            config_id (int): A 16-bit integer id number to identify the config variable.
            type_name (str): An encoded type name that will be parsed by parse_size_name()
            default (object): The default value if there is one.  This should be a
                python object that will be converted to binary according to the rules for
                the config variable type specified in type_name.
            convert (str): whether this variable should be converted to a
                python string or bool rather than an int or a list of ints.  You can
                pass either 'bool', 'string' or None
        """

        config = ConfigDescriptor(config_id, type_name, default, name=name, python_type=convert)
        self._config_variables[config_id] = config

    def reset_config_variables(self):
        """Clear the contents of all config variables to their defaults.

        This method should be used with caution.  It is designed to be called
        during the reset process of a tile in order to properly initialize its
        config variables.
        """

        for config in self._config_variables.values():
            config.clear()

    def latch_config_variables(self):
        """Latch the current value of all config variables as python objects.

        This function will capture the current value of all config variables
        at the time that this method is called.  It must be called after
        start() has been called so that any default values in the config
        variables have been properly set otherwise DataError will be thrown.

        Conceptually this method performs the operation that happens just
        before a tile executive hands control to the tile application
        firmware. It latches in the value of all config variables at that
        point in time.

        For convenience, this method does all necessary binary -> python
        native object conversion so that you just get python objects back.

        Returns:
            dict: A dict of str -> object with the config variable values.

            The keys in the dict will be the name passed to
            `declare_config_variable`.

            The values will be the python objects that result from calling
            latch() on each config variable.  Consult ConfigDescriptor.latch()
            for documentation on how that method works.
        """

        return {desc.name: desc.latch() for desc in self._config_variables.values()}

    def dump_state(self):
        """Dump the current state of this emulated tile as a dictionary.

        This function just dumps the status of the config variables.  It is designed to
        be called in a chained fashion to serialize the complete state of a tile subclass.

        Returns:
            dict: The current state of the object that could be passed to load_state.
        """

        return {
            "config_variables": {x: base64.b64encode(y.current_value).decode('utf-8') for x, y in self._config_variables.items()},
        }

    def restore_state(self, state):
        """Restore the current state of this emulated object.

        Args:
            state (dict): A previously dumped state produced by dump_state.
        """

        config_vars = state.get('config_variables', {})

        for str_name, str_value in config_vars.items():
            name = int(str_name)
            value = base64.b64decode(str_value)

            if name in self._config_variables:
                self._config_variables[name].current_value = value

    def start(self, channel=None):
        """Start any background workers on this tile."""
        pass

    def stop(self):
        """Stop any background workers on this tile."""
        pass

    def _handle_reset(self):
        """Hook to perform any required reset actions.

        Subclasses that override this method should always call
        super()._handle_reset() to make sure their base classes properly
        initialize their reset state.

        The only thing we need to properly do is make sure our config
        variables return to their reset states.
        """

        self.initialized.clear()
        self.reset_config_variables()

    async def _reset_vector(self):
        """Background task that is started when the tile is started.

        This method should be overriden by all tiles that have specific
        background functionality.  It must set the `self.initialized` event
        when it finishes initializing all of the tile's states.
        """

        self.initialized.set()

    async def reset(self):
        """Synchronously reset a tile.

        This method must be called from the emulation loop and will
        synchronously shut down all background tasks running this tile, clear
        it to reset state and then restart the initialization background task.
        """

        await self._device.emulator.stop_tasks(self.address)

        self._handle_reset()

        self._logger.info("Tile at address %d has reset itself.", self.address)

        self._logger.info("Starting main task for tile at address %d", self.address)
        self._device.emulator.add_task(self.address, self._reset_vector())

    @tile_rpc(*rpcs.RESET)
    async def reset_rpc(self):
        """Reset this tile."""
        await self.reset()
        raise TileNotFoundError("tile was reset via an RPC")

    @tile_rpc(*rpcs.LIST_CONFIG_VARIABLES)
    def list_config_variables(self, offset):
        """List defined config variables up to 9 at a time."""

        names = sorted(self._config_variables)
        names = names[offset:offset + 9]
        count = len(names)

        if len(names) < 9:
            names += [0]*(9 - count)

        return [count] + names

    @tile_rpc(*rpcs.DESCRIBE_CONFIG_VARIABLE)
    def describe_config_variable(self, config_id):
        """Describe the config variable by its id."""

        config = self._config_variables.get(config_id)
        if config is None:
            return [Error.INVALID_ARRAY_KEY, 0, 0, 0, 0]

        packed_size = config.total_size
        packed_size |= int(config.variable) << 15

        return [0, 0, 0, config_id, packed_size]

    @tile_rpc(*rpcs.SET_CONFIG_VARIABLE)
    def set_config_variable(self, config_id, offset, value):
        """Set a chunk of the current config value's value."""

        if self.initialized.is_set():
            return [Error.STATE_CHANGE_AT_INVALID_TIME]

        config = self._config_variables.get(config_id)
        if config is None:
            return [Error.INVALID_ARRAY_KEY]

        error = config.update_value(offset, value)
        return [error]

    @tile_rpc(*rpcs.GET_CONFIG_VARIABLE)
    def get_config_variable(self, config_id, offset):
        """Get a chunk of a config variable's value."""

        config = self._config_variables.get(config_id)
        if config is None:
            return [b""]

        return [bytes(config.current_value[offset:offset + 20])]

    @tile_rpc(*rpcs.TILE_STATUS)
    def tile_status(self):
        """Required status RPC that allows matching a proxy object with a tile."""

        #TODO: Make this status real based on the tile's status

        status = (1 << 1) | (1 << 0)  # Configured and running, not currently used but required for compat with physical tiles
        return [0xFFFF, self.name, 1, 0, 0, status]



TYPE_CODES = {'uint8_t': 'B', 'char': 'B', 'int8_t': 'b', 'uint16_t': 'H', 'int16_t': 'h', 'uint32_t': 'L', 'int32_t': 'l'}


def parse_size_name(type_name):
    """Calculate size and encoding from a type name.

    This method takes a C-style type string like uint8_t[10] and returns
    - the total size in bytes
    - the unit size of each member (if it's an array)
    - the scruct.{pack,unpack} format code for decoding the base type
    - whether it is an array.
    """

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
