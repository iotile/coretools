"""Well-known global error codes that can be returned by emulated RPCs."""

NO_ERROR = 0
"""No error occurred."""

STATIC_MEMORY_ALLOCATION_ERROR = 1
"""There was an error allocating static memory."""

ERROR_IN_ROM_DRIVER = 2
"""There was an error inside a third party ROM driver."""

INPUT_BUFFER_TOO_LONG = 3
"""The input buffer was too long."""

SETUP_FUNCTION_PERFORMED_TWICE = 4
"""A setup function was performed twice."""

REQUIRED_SETUP_NOT_PERFORMED = 5
"""A required setup function was not performed."""

INVALID_ARRAY_KEY = 6
"""An invalid array key was passed."""

INVALID_CHECKSUM = 7
"""An object had an invalid checksum."""

INVALID_OFFSET = 8
"""An invalid offset was given."""

STATE_CHANGE_AT_INVALID_TIME = 9
"""The state of an object changed at an unexpected time."""

TIMEOUT_ERROR = 10
"""An operation has timed out."""

UNIMPLEMENTED_ERROR = 11
"""The requested operation is not (yet) implemented."""

UNKNOWN_ERROR = 12
"""An unknown error occurred."""

HARDWARE_PERIPHERAL_ERROR = 13
"""An internal hardware peripheral inside the microcontroller or SOC had a failure."""

EXTERNAL_HARDWARE_ERROR = 14
"""An external hardware device had an unrecoverable failure."""

INVALID_UNALIGNED_ADDRESS = 15
"""A request was made for for an unaligned memory address."""

DESTINATION_BUFFER_TOO_SMALL = 16
"""The destination buffer is too small."""

INPUT_BUFFER_WRONG_SIZE = 17
"""The input buffer passed was the wrong size."""

LOW_VOLTAGE_WARNING = 18
"""An observed voltage triggered a low-voltage warning."""

HIGH_VOLTAGE_WARNING = 19
"""An observed voltage triggered a high-voltage warning."""

INVALID_VOLTAGE_ERROR = 20
"""An observed voltage was invalid."""

INPUT_BUFFER_TOO_SMALL = 21
"""The input buffer passed was too small."""

INVALID_MAGIC_NUMBER = 22
"""An magic number did not match its expected value."""

INVALID_HASH_VALUE = 23
"""A calculated hash value did not match its expected value."""

UNALIGNED_VARIABLE_ERROR = 24
"""A variable was not properly aligned."""
