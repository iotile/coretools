"""These RPCs implement the configuration variable interface of any tile.

Config variables are used to stream configuration information to a tile when
it resets, before any application firmware is run.  All tiles must implement
these RPCs in order to allow for boot-time configuration.

The local IOTile controller is in charge of persisting and streaming the
actual config variables to each tile, these RPCs just provide the API that it
can use in order to do so.
"""

from iotile.core.hw.virtual import RPCDeclaration


LIST_CONFIG_VARIABLES = RPCDeclaration(10, "H", "H9H")
"""Iteratively list all defined config variables on this tile.

This method returns a chunk of the tile's internal config variable declaration
table.  You pass an offset as an argument and it returns the config_variable
ids of the next 9 config variables prepended with a valid count.  The return
value of this RPC is fixed size so the count value will tell you how many
entries are valid.

Clients should call this function repeatedly incrementing the offset until
count is returned as 0 indicating that the table has been exhausted.

Args:
  - uint16_t: An offset into the tile's config variable table.

Returns:
  - uint16_t: The count of valid config variable ids that follow.  This will
    always be [0, 9] inclusive.
  - uint16_t[9]: An array of 16 bit config variable ids.  Only the first count
    entries are valid and the order is unspecified but usually sorted lowest
    to highest.
"""

DESCRIBE_CONFIG_VARIABLE = RPCDeclaration(11, "H", "HHLHH")
"""Describe the type, size and internal address of a config variable by id.

This method returns the internal config variable descriptor for a given
config variable by its 16-bit config id.  When an error is returned the
contents of the rest of the response are undefined.

Args:
  - uint16_t: The config variable ID you wish to inspect.  This should
    be in the list returned by LIST_CONFIG_VARIABLES or an error will
    be returned.

Returns:
  - uint16_t: An error code, otherwise NO_ERROR to indicate success.
  - uint16_t: Reserved for alignment, value is undefined.
  - uint32_t: The internal RAM address of this config variable.  There
    is typically no need to use this value for anything but it could
    be useful for advanced debugging scenarios.
  - uint16_t: The config variable id of this variable, will always
    match what you passed in the arguments.
  - uint16_t: Encoded bit field.  The low 15 bits are the total
    size of the space allocated for this config variable in bytes.
    The high bit indicates whether this is an array or a single
    value.

Possible Errors:
  - INVALID_ARRAY_KEY: The config variable id could not be found
"""

SET_CONFIG_VARIABLE = RPCDeclaration(12, "HHV", "H")
"""Set a chunk (possibly all) of the config variable's value.

Config variables for the purposes of set and get are treated as binary strings
of bytes.  This function lets you stream in up to 20 bytes of data into the
config variable at the specified offset.

Variable length config variables keep track of the highest offset written to
by a call SET_CONFIG_VARIABLE and report that as their size.  For that reason
it is important to send data to a long config variable from low to high
offsets so that the final length is correct.  Writing to a low offset after
having previously written to a high offset will truncate the stored data.

If an error is returned, the state of the config variable is unchanged by this
call.

Args:
  - uint16_t: the id of the config variable that you want to set.
  - uint16_t: The offset that you want to start writing at.
  - char[]: Variable length buffer up to the end of the RPC payload that will
    be copied into the variable's value starting at the specified offset.

Returns:
  - uint16_t: An error code.

Possible Errors:
  - INVALID_ARRAY_KEY: The config variable id could not be found
  - STATE_CHANGE_AT_INVALID_TIME: This RPC was called after a peripheral
    tile's firmware had already started execution. Config variable are not
    allowed to change while a tile is running.
  - INPUT_BUFFER_TOO_LONG: The data would overflow the space allocated for the
    config variable.
"""

GET_CONFIG_VARIABLE = RPCDeclaration(13, "HH", "V")
"""Get a chunk (possibly all) of the config variable's value.

Config variables for the purposes of set and get are treated as binary strings
of bytes.  This function lets you get up to 20 bytes of data into the config
variable at the specified offset.

Callers should call this function repeatedly with incrementing offset until
it returns 0 bytes indicating that you have received all data from that
config variable.

There is no way for the tile to communicate to you that the call failed except
by returning a 0-length result so you cannot tell the difference with this
call between a config variable that does not exist and one that has variable
size and no data written yet.

Fixed size config variables will always return their fixed size regardless of
how much data has been written to them.

Args:
  - uint16_t: the id of the config variable that you want to set.
  - uint16_t: The offset that you want to start writing at.

Returns:
  - char[]: Up to 20 bytes of data from the config variable starting at the
    given offset.  The return value may be smaller than 20 bytes if the end
    of the data is reached.
"""
