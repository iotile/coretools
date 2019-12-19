"""Exceptions that can be thrown from BLE operations."""

from typing import Optional

class BluetoothError(Exception):
    """Base exception for all bluetooth related errors."""

    def __init__(self, message):
        super(BluetoothError, self).__init__()
        self.message = message


class UnsupportedOperationError(BluetoothError):
    """Operations that the underlying bluetooth hardware or driver don't support."""


class InvalidStateError(BluetoothError):
    """Operation was requested when the adapter was in an invalid state to respond."""


class FatalAdapterError(BluetoothError):
    """Fatal errors inside the bluetooth adapter hardware that are unrecoverable."""


class LinkError(BluetoothError):
    """Errors that are specific to a single remote connection."""

    def __init__(self, message: str, conn_string: Optional[str]):
        super(LinkError, self).__init__(message)
        self.connection_string = conn_string


# Link Operation related errors
class QueueFullError(LinkError):
    """An operation could not be queued, it should be retried.

    This can be for a number of reasons where internal buffers in the ble
    controller are filled by commands and emptied across the wire at the next
    connection interval.  An example is BLE notifications, which can send 3-6
    per connection interval and are buffered in the meantime.  If you push
    notifications faster than 3-6 per connection interval, the notify()
    command will start to fail since the queue is full.

    This error means you need to backoff and try again.  It is not a fatal
    error and often an expected part of link flow control.
    """


class GattError(LinkError):
    """An operation could not be completed because of an invalid GATT state.

    The message will provide more information on what the issue was.
    """


class InvalidHandleError(GattError):
    """There was a generic error with an operation on a specific gatt handle."""

    def __init__(self, message: str, handle: int, conn_string: Optional[str] = None):
        super(InvalidHandleError, self).__init__(message, conn_string)
        self.handle = handle


class MissingHandleError(InvalidHandleError):
    """An operation was attempted on a gatt handle that did not exist."""

    def __init__(self, handle: int, conn_string: Optional[str] = None):
        super(MissingHandleError, self).__init__("Handle 0x%02x did not exist" % handle, handle, conn_string)


# Disconnection related errors
class DisconnectionError(LinkError):
    """Error raised when a remote device is disconnected."""

    LOCAL_DISCONNECT = 1
    EARLY_DISCONNECT = 2
    SUPERVISION_TIMEOUT = 3
    UNKNOWN_ERROR = -1

    def __init__(self, message: str, conn_string: str, reason: int = UNKNOWN_ERROR):
        super(DisconnectionError, self).__init__(message, conn_string)
        self.reason = reason


class EarlyDisconnectError(DisconnectionError):
    """Disconnection error due to a failed connection attempt.

    The bluetooth standard specifies that after a connection attempt is made,
    it is optimistically assumed to work.  However if the next packet sent
    does not succeed then the connection attempt is abandoned with an
    EarlyDisconnect error."""

    def __init__(self, conn_string: str):
        super(EarlyDisconnectError, self).__init__("Early disconnect from %s" % conn_string,
                                                   conn_string, DisconnectionError.EARLY_DISCONNECT)


class LocalDisconnectError(DisconnectionError):
    """Disconnection because the user requested it."""

    def __init__(self, conn_string: str):
        super(LocalDisconnectError, self).__init__("Locally initiated disconnect from %s" % conn_string,
                                                   conn_string, DisconnectionError.LOCAL_DISCONNECT)


class SupervisionTimeoutError(DisconnectionError):
    """Disconnection because the remote device did not respond quickly enough.

    The link supervision timeout is configured for each connection and is the
    maximum time that a remote device can go without communicating
    successfully with its peer.
    """

    def __init__(self, conn_string: str):
        super(SupervisionTimeoutError, self).__init__("Locally initiated disconnect from %s" % conn_string,
                                                      conn_string, DisconnectionError.LOCAL_DISCONNECT)
