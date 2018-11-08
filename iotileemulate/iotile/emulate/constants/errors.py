"""Well-known global error codes that can be returned by emulated RPCs."""

from enum import IntEnum

class Error(IntEnum):
    """All globally defined common errors that an RPC may report."""

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


class ConfigDatabaseError(IntEnum):
    """These are subsystem specific error codes potentially returned by the ConfigDatabase."""

    OBSOLETE_ENTRY = 0x8000
    """The config variable entry requested has been invalidated."""

    VARIABLE_DOES_NOT_MATCH = 0x8001
    """The requested config variable does not match."""

    INVALID_ENTRY = 0x8002
    """The requested config variable entry has an invalid magic number."""


class SensorLogError(IntEnum):
    """These are subsystem specific error codes potentially returned by the SensorLog."""

    NO_MORE_READINGS = 0x8000
    """There are no more available readings."""

    VIRTUAL_STREAM_NOT_FOUND = 0x8001
    """There is no stream walker allocated for a specific virtual stream."""

    STREAM_WALKER_NOT_FOUND = 0x8002
    """Could not find the desired stream walker."""

    IMMEDIATE_VALUE_NOT_SUPPORTED = 0x8003
    """This stream does not support immediate values."""

    CANNOT_SKIP_INEXHAUSTIBLE_STREAM = 0x8004  #pylint:disable=invalid-name;This is the name.
    """You cannot call skip on a constant stream that is infinitely deep."""

    STREAM_WALKER_NOT_INITIALIZED = 0x8005
    """The stream walker structure was not properly initialized."""

    CANNOT_USE_UNBUFFERED_STREAM = 0x8006
    """This method cannot use an unbuffered stream."""

    ID_FOUND_FOR_ANOTHER_STREAM = 0x8007
    """Seek_id was called and the id was found but belonged to another stream."""

    RING_BUFFER_FULL = 0x8008
    """The RSL is in fill-stop mode and the desired storage area is full."""


class SensorGraphError(IntEnum):
    """These are subsystem specific error coded potentially returned by SensorGraph."""

    INVALID_NODE_INDEX = 0x8000

    UNINITIALIZED_NODE = 0x8001

    NODE_ALREADY_INITIALIZED = 0x8002

    INVALID_INPUT_INDEX = 0x8003

    NO_PROCESSING_FUNCTION = 0x8004

    NO_UPDATED_OUTPUT = 0x8005

    GRAPH_OFFLINE = 0x8006

    TASK_ALREADY_PENDING = 0x8007

    READING_IGNORED = 0x8008

    INVALID_PROCESSING_FUNCTION = 0x8009

    NO_AVAILABLE_OUTPUTS = 0x800A

    STREAM_NOT_IN_USE = 0x800B

    NO_NODE_SPACE_AVAILABLE = 0x800C

    INVALID_NODE_STREAM = 0x800D

    STREAM_ALREADY_IN_USE = 0x800E

    NODE_NOT_TRIGGERED = 0x800F

    INVALID_STREAM_DESTINATION = 0x8010

    STREAM_ALREADY_IN_PROGRESS = 0x8011

    ERROR_STARTING_STREAMING = 0x8012

    NO_MORE_STREAMER_RESOURCES = 0x8013

    NO_PERSISTED_GRAPH = 0x8014

    OLD_PERSISTED_GRAPH = 0x8015

    INVALID_PERSISTED_GRAPH = 0x8016

    INVALID_BACKOFF_STRATEGY = 0x8017

    STREAMER_NOT_ALLOCATED = 0x8018

    BACKOFF_IN_PROGRESS = 0x8019

    NO_MORE_SELECTOR_NAMES = 0x801A

    UNKNOWN_SELECTOR_NAME = 0x801B

    SELECTOR_DOES_NOT_MATCH_MODULE = 0x801C

    TOO_MANY_ROOT_NODES = 0x801D

    OLD_ACKNOWLEDGE_UPDATE = 0x801E

    STREAMER_HAS_NO_NEW_DATA = 0x801F

    STREAMER_NOT_TRIGGERED = 0x8020
