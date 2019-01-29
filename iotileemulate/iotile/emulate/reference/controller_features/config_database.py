"""Mixin for persistent database of config variables to send to tiles on reset."""

import base64
import struct
from iotile.core.exceptions import ArgumentError, DataError
from iotile.core.hw.virtual import tile_rpc
from iotile.sg import SlotIdentifier
from ...virtual import SerializableState
from ...constants import Error, ConfigDatabaseError, rpcs


class ConfigEntry(object):
    """Data class representing a single config variable entry."""

    CONTROL_SIZE = 16

    def __init__(self, selector, var_id, data, valid=True):
        self.target = selector
        self.var_id = var_id
        self.data = data
        self.valid = valid

    def control_space(self):
        """Return how much control space this entry uses."""
        return self.CONTROL_SIZE

    def data_space(self):
        """Return how much data space this entry uses.

        The variable target is stored prepended to the data so even if there
        is no actual data, there are always two bytes used.

        Returns:
            int
        """

        return len(self.data)

    def dump(self):
        """Serialize this object."""

        return {
            'target': str(self.target),
            'data': base64.b64encode(self.data).decode('utf-8'),
            'var_id': self.var_id,
            'valid': self.valid
        }

    def generate_rpcs(self, address):
        """Generate the RPCs needed to stream this config variable to a tile.

        Args:
            address (int): The address of the tile that we should stream to.

        Returns:
            list of tuples: A list of argument tuples for each RPC.

            These tuples can be passed to EmulatedDevice.rpc to actually make
            the RPCs.
        """

        rpc_list = []

        for offset in range(2, len(self.data), 16):
            rpc = (address, rpcs.SET_CONFIG_VARIABLE, self.var_id, offset - 2, self.data[offset:offset + 16])
            rpc_list.append(rpc)

        return rpc_list

    @classmethod
    def Restore(cls, state):
        """Unserialize this object."""

        target = SlotIdentifier.FromString(state.get('target'))
        data = base64.b64decode(state.get('data'))
        var_id = state.get('var_id')
        valid = state.get('valid')

        return ConfigEntry(target, var_id, data, valid)


class ConfigDatabase(SerializableState):
    """Emulated state of the config database.

    Args:
        control_size (int): The number of bytes reserved for storing control
            and targeting information.
        data_size (int): The number of bytes reseved for storing config data.
    """

    ENTRY_MAGIC = 0xcaca

    def __init__(self, control_size, data_size):
        super(ConfigDatabase, self).__init__()

        self.control_size = control_size
        self.data_size = data_size
        self.entries = []
        self.in_progress = None
        self.data_index = 0

        self.mark_complex('entries', lambda entries: [x.dump() for x in entries], lambda entries: [ConfigEntry.Restore(x) for x in entries])

    def max_entries(self):
        """Calculate the maximum number of config variables that we can store."""

        return self.control_size // ConfigEntry.CONTROL_SIZE - 1

    def compact(self):
        """Remove all invalid config entries."""

        saved_length = 0
        to_remove = []
        for i, entry in enumerate(self.entries):
            if not entry.valid:
                to_remove.append(i)
                saved_length += entry.data_space()

        for i in reversed(to_remove):
            del self.entries[i]

        self.data_index -= saved_length

    def clear(self):
        """Clear all config variables stored in this config database."""

        self.entries = []
        self.in_progress = None
        self.data_index = 0

    def start_entry(self, target, var_id):
        """Begin a new config database entry.

        If there is a current entry in progress, it is aborted but the
        data was already committed to persistent storage so that space
        is wasted.

        Args:
            target (SlotIdentifer): The target slot for this config variable.
            var_id (int): The config variable ID

        Returns:
            int: An error code from the global Errors enum.
        """

        self.in_progress = ConfigEntry(target, var_id, b'')

        if self.data_size - self.data_index < self.in_progress.data_space():
            return Error.DESTINATION_BUFFER_TOO_SMALL

        self.in_progress.data += struct.pack("<H", var_id)
        self.data_index += self.in_progress.data_space()

        return Error.NO_ERROR

    def add_data(self, data):
        """Add data to the currently in progress entry.

        Args:
            data (bytes): The data that we want to add.

        Returns:
            int: An error code
        """

        if self.data_size - self.data_index < len(data):
            return Error.DESTINATION_BUFFER_TOO_SMALL

        if self.in_progress is not None:
            self.in_progress.data += data

        return Error.NO_ERROR

    def end_entry(self):
        """Finish a previously started config database entry.

        This commits the currently in progress entry.  The expected flow is
        that start_entry() is called followed by 1 or more calls to add_data()
        followed by a single call to end_entry().

        Returns:
            int: An error code
        """

        # Matching current firmware behavior
        if self.in_progress is None:
            return Error.NO_ERROR

        # Make sure there was actually data stored
        if self.in_progress.data_space() == 2:
            return Error.INPUT_BUFFER_WRONG_SIZE

        # Invalidate all previous copies of this config variable so we
        # can properly compact.
        for entry in self.entries:
            if entry.target == self.in_progress.target and entry.var_id == self.in_progress.var_id:
                entry.valid = False

        self.entries.append(self.in_progress)
        self.data_index += self.in_progress.data_space() - 2  # Add in the rest of the entry size (we added two bytes at start_entry())
        self.in_progress = None

        return Error.NO_ERROR

    def stream_matching(self, address, name):
        """Return the RPCs needed to stream matching config variables to the given tile.

        This function will return a list of tuples suitable for passing to
        EmulatedDevice.deferred_rpc.

        Args:
            address (int): The address of the tile that we wish to stream to
            name (str or bytes): The 6 character name of the target tile.

        Returns:
            list of tuple: The list of RPCs to send to stream these variables to a tile.
        """

        matching = [x for x in self.entries if x.valid and x.target.matches(address, name)]

        rpc_list = []
        for var in matching:
            rpc_list.extend(var.generate_rpcs(address))

        return rpc_list

    def add_direct(self, target, var_id, var_type, data):
        """Directly add a config variable.

        This method is meant to be called from emulation scenarios that
        want to directly set config database entries from python.

        Args:
            target (SlotIdentifer): The target slot for this config variable.
            var_id (int): The config variable ID
            var_type (str): The config variable type
            data (bytes or int or str): The data that will be encoded according
                to var_type.
        """

        data = struct.pack("<H", var_id) + _convert_to_bytes(var_type, data)

        if self.data_size - self.data_index < len(data):
            raise DataError("Not enough space for data in new conig entry", needed_space=len(data), actual_space=(self.data_size - self.data_index))

        new_entry = ConfigEntry(target, var_id, data)

        for entry in self.entries:
            if entry.target == new_entry.target and entry.var_id == new_entry.var_id:
                entry.valid = False

        self.entries.append(new_entry)
        self.data_index += new_entry.data_space()


class ConfigDatabaseMixin(object):
    """Persistent data of config variables.

    These variables are targeted at at a tile and are automatically streamed
    to that tile when it registers.

    The config variables are stored as binary blobs in flash memory with a
    fixed area of flash reserved for them.

    The config database is implemented

    Args:
        control_size (int): The number of bytes reserved for storing control
            and targeting information.
        data_size (int): The number of bytes reseved for storing config data.
    """

    def __init__(self, control_size, data_size):
        self.config_database = ConfigDatabase(control_size, data_size)

    @tile_rpc(*rpcs.START_CONFIG_VAR_ENTRY)
    def start_config_var_entry(self, var_id, encoded_selector):
        """Start a new config variable entry."""

        selector = SlotIdentifier.FromEncoded(encoded_selector)

        err = self.config_database.start_entry(selector, var_id)
        return [err]

    @tile_rpc(*rpcs.CONTINUE_CONFIG_VAR_ENTRY)
    def continue_config_var_entry(self, data):
        """Push data to the current config variable entry."""

        err = self.config_database.add_data(data)
        return [err]

    @tile_rpc(*rpcs.END_CONFIG_VAR_ENTRY)
    def end_config_var_entry(self):
        """Finish the currently in progress config variable entry."""

        err = self.config_database.end_entry()
        return [err]

    @tile_rpc(*rpcs.GET_CONFIG_VAR_ENTRY)
    def get_config_var_entry(self, index):
        """Get the metadata from the selected config variable entry."""

        if index == 0 or index > len(self.config_database.entries):
            return [Error.INVALID_ARRAY_KEY, 0, 0, 0, b'\0'*8, 0, 0]

        entry = self.config_database.entries[index - 1]
        if not entry.valid:
            return [ConfigDatabaseError.OBSOLETE_ENTRY, 0, 0, 0, b'\0'*8, 0, 0]

        offset = sum(x.data_space() for x in self.config_database.entries[:index - 1])
        return [Error.NO_ERROR, self.config_database.ENTRY_MAGIC, offset, entry.data_space(), entry.target.encode(), 0xFF, 0]

    @tile_rpc(*rpcs.COUNT_CONFIG_VAR_ENTRIES)
    def count_config_var_entries(self):
        """Count how many config variables have been saved."""

        return [len(self.config_database.entries)]

    @tile_rpc(*rpcs.CLEAR_CONFIG_VAR_ENTRIES)
    def clear_config_var_entries(self):
        """Clear all currently stored config variables."""

        self.config_database.clear()
        return [Error.NO_ERROR]

    @tile_rpc(*rpcs.GET_CONFIG_VAR_ENTRY_DATA)
    def get_config_var_data(self, index, offset):
        """Get a chunk of data for a config variable."""

        if index == 0 or index > len(self.config_database.entries):
            return [Error.INVALID_ARRAY_KEY, b'']

        entry = self.config_database.entries[index - 1]
        if not entry.valid:
            return [ConfigDatabaseError.OBSOLETE_ENTRY, b'']

        if offset >= len(entry.data):
            return [Error.INVALID_ARRAY_KEY, b'']

        data_chunk = entry.data[offset:offset + 16]
        return [Error.NO_ERROR, data_chunk]

    @tile_rpc(*rpcs.INVALIDATE_CONFIG_VAR_ENTRY)
    def invalidate_config_var_entry(self, index):
        """Mark a config variable as invalid."""

        if index == 0 or index > len(self.config_database.entries):
            return [Error.INVALID_ARRAY_KEY, b'']

        entry = self.config_database.entries[index - 1]
        if not entry.valid:
            return [ConfigDatabaseError.OBSOLETE_ENTRY, b'']

        entry.valid = False
        return [Error.NO_ERROR]

    @tile_rpc(*rpcs.COMPACT_CONFIG_DATABASE)
    def compact_config_database(self):
        """Compact the config database, removing any invalid entries."""

        self.config_database.compact()
        return [Error.NO_ERROR]

    @tile_rpc(*rpcs.GET_CONFIG_DATABASE_INFO)
    def get_config_database_info(self):
        """Get memory usage and space statistics on the config database."""

        max_size = self.config_database.data_size
        max_entries = self.config_database.max_entries()
        used_size = self.config_database.data_index
        used_entries = len(self.config_database.entries)
        invalid_size = sum(x.data_space() for x in self.config_database.entries if not x.valid)
        invalid_entries = sum(1 for x in self.config_database.entries if not x.valid)

        return [max_size, used_size, invalid_size, used_entries, invalid_entries, max_entries, 0]


def _convert_to_bytes(type_name, value):
    """Convert a typed value to a binary array"""

    int_types = {'uint8_t': 'B', 'int8_t': 'b', 'uint16_t': 'H', 'int16_t': 'h', 'uint32_t': 'L', 'int32_t': 'l'}

    type_name = type_name.lower()

    if type_name not in int_types and type_name not in ['string', 'binary']:
        raise ArgumentError('Type must be a known integer type, integer type array, string', known_integers=int_types.keys(), actual_type=type_name)

    if type_name == 'string':
        #value should be passed as a string
        bytevalue = bytes(value)
    elif type_name == 'binary':
        bytevalue = bytes(value)
    else:
        bytevalue = struct.pack("<%s" % int_types[type_name], value)

    return bytevalue
