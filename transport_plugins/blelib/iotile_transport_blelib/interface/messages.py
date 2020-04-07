"""Abstract definition of high level messages that can be sent from an AbstractBLECentral.

These messages are designed to correspond closely enough with low level HCI packets that
they are easy to generate on a wide variety of bluetooth hardware, but high level enough
to avoid needing
"""

from typing import Optional
from .gatt import GattCharacteristic
from .peripheral import BLEPeripheral
from .advertisement import BLEAdvertisement
from .errors import DisconnectionError

class BluetoothEvent:
    """Base class for all events sent from a bluetooth driver."""

    event = None  #type: Optional[str]
    category = None  #type: Optional[str]


class PeripheralConnected(BluetoothEvent):
    """Event sent when a connection to a peripheral has been established.

    This message will always be sent exactly once for a connection and will
    precede any other link related messages.  It will always be followed by
    exactly one disconnection message once the peripheral connection has
    terminated for any reason.
    """

    def __init__(self, peripheral: BLEPeripheral):
        self.event = "peripheral_connected"
        self.link = peripheral.connection_string  #type: str
        self.peripheral = peripheral  #type: BLEPeripheral


class PeripheralDisconnected(BluetoothEvent):
    """Event sent when a connection to a peripheral is lost.

    This message will only be sent after a PeripheralConnection message for
    the same peripheral has been sent.  It will always be the final message
    sent for a given peripheral.
    """

    def __init__(self, peripheral: BLEPeripheral, expected: bool,
                 exception: Optional[DisconnectionError] = None):

        self.event = "peripheral_disconnected"
        self.link = peripheral.connection_string  #type: str
        self.peripheral = peripheral  #type: BLEPeripheral
        self.expected = expected  #type: bool
        self.error = exception  #type: Optional[DisconnectionError]


class NotificationReceived(BluetoothEvent):
    """Event sent when a characteristic notification is received."""

    def __init__(self, peripheral: BLEPeripheral, characteristic: GattCharacteristic,
                 value: bytes):
        self.event = "notification"
        self.link = peripheral.connection_string
        self.peripheral = peripheral
        self.characteristic = characteristic
        self.value = value


class AdvertisementObserved(BluetoothEvent):
    """Event sent when an ble advertisement is seen."""

    def __init__(self, advertisement: BLEAdvertisement, active_scan: bool):
        self.category = "scanning"
        self.event = "advertisement"  #type: str
        self.sender = advertisement.sender  #type: str
        self.advertisement = advertisement  #type: BLEAdvertisement
        self.active_scan = active_scan  #type: bool


class ScanningStarted(BluetoothEvent):
    """Event sent when scanning for devices has begun."""

    def __init__(self, active_scan: bool):
        self.category = "scanning"
        self.event = "scanning_started"
        self.active_scan = active_scan


class ScanningStopped(BluetoothEvent):
    """Event sent when scanning for devices has stopped.

    Stopping could either be because a user requested that scanning be stopped
    or because the underlying hardware needed to stop scanning in order to
    perform another operation.
    """

    def __init__(self):
        self.category = "scanning"
        self.event = "scanning_stopped"
