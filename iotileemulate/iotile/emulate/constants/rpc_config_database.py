"""RPCs implemented by the ConfigDatabase subsystem on an IOTile controller tile.

These RPCs allow you to persistently store config variables that will be
streamed to specific tiles on each reset.  This is analogous to how
Environment Variables work on unix with the config variable being an
Environment Variable and the tile being a process.

The variables are sent to each tile when the tiles boot and their values do
not change during the lifetime of the tile.
"""

from iotile.core.hw.virtual import RPCDeclaration


START_CONFIG_VAR_ENTRY = RPCDeclaration(0x2a07, "H8s", "L")
"""Start pushing a new config variable to the ConfigDatabase.

The expected use of this RPC is the following sequence:
- START_CONFIG_VAR_ENTRY
- CONTINUE_CONFIG_VAR_ENTRY (1 or more times as needed)
- END_CONFIG_VAR_ENTRY

This series of RPCs will add save config var into the config database.

Args:
  - uint16_t: The config var id that we are sending such as 0x8001
  - char[8]: A serialized SlotIdentifier object that will be used to
    decide which tile(s) this config variable will be sent to.

Returns:
  - uint32_t: An error code.

Possible Errors:
  - STATE_CHANGE_AT_INVALID_TIME: If a config database compaction is in progress.
  - DESTINATION_BUFFER_TOO_SMALL: If there is not enough space for the config variable
    data.
"""

CONTINUE_CONFIG_VAR_ENTRY = RPCDeclaration(0x2a08, "V", "L")
"""Push data to the config variable entry currently in progress.

This RPC should only be called after START_CONFIG_VAR_ENTRY.  The contents
of the RPC call are just a binary blob of data that will be appened to the
current config variable.

You can call this RPC multiple times to push more than 20 bytes of data.

Args:
  - char[]: The binary data that should be appended to the config variable
    in the database.

Returns:
  - uint32_t: An error code.

Possible Errors:
  - DESTINATION_BUFFER_TOO_SMALL: If there is not enough space for the config variable
    data.
"""

END_CONFIG_VAR_ENTRY = RPCDeclaration(0x2a09, "", "L")
"""Finish the current config variable entry.

This RPC is called to commit whatever data has been pushed with previous calls
to CONTINUE_CONFIG_VAR_ENTRY and mark the currently in-progress config var as
complete.

Returns:
  - uint32_t: An error code.

Possible Errors:
  - INPUT_BUFFER_WRONG_SIZE: If the length of the config variable is 0, indicating no previous
    calls to CONFIG_CONFIG_VAR_ENTRY.
"""

GET_CONFIG_VAR_ENTRY = RPCDeclaration(0x2a0a, "H", "L3H8sBB")
"""Get a raw config variable entry by index.

This RPC will return the raw control entry for a config variable
stored in the config database.  The argument is the index of the
variable to get which should be in the range [1, COUNT_CONFIG_VAR_ENTRIES].

Note that the index is one-based since the 0th spot is reserved for magic
number information.

Args:
  - uint16_t: The 1-based index of the config variable entry you want to
    dump.

Returns:
  - uint32_t: An error code.
  - uint16_t: A magic number
  - uint16_t: The raw offset where data starts for this config variable in
    the data storage buffer.
  - uint16_t: The length of data in bytes that is associated with this config
    variable. Note that the config variable id is stored as the first 2 bytes
    of the config data so this will always be greater than 2.
  - char[8]: An encoded SlotIdentifier specifying the target information for
    the config variable.
  - uint8_t: Whether this config entry is still valid.  This will be 0xFF if
    valid.  If not valid, an error will be returned instead so you will never
    see a non-0xFF value here.
  - uint8_t: Reserved, should be ignored.

Possible Errors:
  - STATE_CHANGE_AT_INVALID_TIME: A database compaction is in progress.
  - INVALID_ARRAY_KEY: The index is < 1 or > the number of stored entries.
  - OBSOLETE_ENTRY: The entry has been marked as invalid.
  - INVALID_ENTRY: The entry has an invalid magic number.  This usually indicates
    some kind of database corruption.
"""

COUNT_CONFIG_VAR_ENTRIES = RPCDeclaration(0x2a0b, "", "L")
"""Count the number of stored config variables.

Returns:
  - uint32_t: The count of currently stored config variables including
    variables that have been marked as invalid.  This number will only
    ever decrease after a call to CLEAR_CONFIG_VAR_ENTRIES or
    COMPACT_CONFIG_VAR_ENTRIES.
"""

CLEAR_CONFIG_VAR_ENTRIES = RPCDeclaration(0x2a0c, "", "L")
"""Clear all config variables from the config database.

If database compaction is currently in progress, the function will
return without doing anything and without setting any error code.

Returns:
  - uint32_t: An error code.  No possible errors can be returned
    currently.
"""

GET_CONFIG_VAR_ENTRY_DATA = RPCDeclaration(0x2a0d, "HH", "LV")
"""Get up to 16 bytes of data from a config variable entry.

This RPC take a 1-based index for the variable you want to read
and an offset into the data defined for that variable.  It
returns the next 16-bytes of data starting at that offset.  If
there are less than 16-bytes of data left, it returns less data.

Args:
  - uint16_t: The 1 based index of the config variable we want data from.
  - uint16_t: The offset of the the chunk of data that we want to receive.

Returns:
  - uint32_t: An error code.
  - char[]: Up to 16 bytes of binary data from the selected config variable.

Possible Errors:
  - INVALID_ARRAY_KEY: The index is < 1 or > the number of stored entries or
    the index is valid but the offset is invalid for the length of that entry.
  - OBSOLETE_ENTRY: The entry has been marked as invalid.
  - INVALID_ENTRY: The entry has an invalid magic number.  This usually
    indicates some kind of database corruption.
"""

INVALIDATE_CONFIG_VAR_ENTRY = RPCDeclaration(0x2a0e, "H", "L")
"""Invalidate a config variable entry by index.

This RPC will mark the corresponding config variable as invalid. This
operation effectively erases the config variable but since the data is stored
in an append-only log format, it does not actually free any storage.  The only
way to reclaim the space used by invalidated config entries is by calling the
COMPACT_CONFIG_DATABASE rpc.

Args:
  - uint16_t: The 1 based index of the config variable we want data from.

Returns:
  - uint32_t: An error code.

Possible Errors:
  - INVALID_ARRAY_KEY: The index is < 1 or > the number of stored entries or
    the index is valid but the offset is invalid for the length of that entry.
  - OBSOLETE_ENTRY: The entry has been marked as invalid.
  - INVALID_ENTRY: The entry has an invalid magic number.  This usually
    indicates some kind of database corruption.
"""

COMPACT_CONFIG_DATABASE = RPCDeclaration(0x2a0f, "", "L")
"""Compact the config database by removing all invalid entries.

This RPC will perform garbage collection synchronously on the config database.
Any entries marked as invalid will be removed and the remaining entries will
be shifted left to fill in the space left by the missing entries.

Returns:
  - uint32_t: An error code.  This method cannot fail.
"""

GET_CONFIG_DATABASE_INFO = RPCDeclaration(0x2a10, "", "L6H")
"""Get memory usage and space information about the config database.

This RPC returns a set of useful information about the state of the
config database including how many entries are there, how many are
invalid and how much space count be saved by compacting the database.

Returns:
  - uint32_t: The maximum number of data bytes that can be stored.
  - uint16_t: The current size of all data bytes stored.
  - uint16_t: The current size of all invalid config variables that
    could be saved by compaction.
  - uint16_t: The current count of all stored config variables.
  - uint16_t: The current count of all invalid config variables that
    would be removed by compaction.
  - uint16_t: The maximum number of config variables that can be stored.
  - uint16_t: Reserved.
"""
