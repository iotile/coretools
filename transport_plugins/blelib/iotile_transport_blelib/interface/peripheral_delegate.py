"""Base interface defining an object that receives callbacks when events occur on a ble connection."""

from typing import Protocol
from .gatt import GattCharacteristic
from .peripheral import BLEPeripheral


class BLEPeripheralDelegate(Protocol):
    """Delegate invoked whenever specific events happen on a connected ble peripheral.

    This delegate is the primary way by which asynchronous information is
    passed from the BLE peripheral to the user that connected it.

    If information is needed from the user, appropriate callbacks will also be
    invoked, such as providing security keys or other pairing or connection
    information.
    """

    def on_notification(self, peripheral: BLEPeripheral, characteristic: GattCharacteristic,
                        value: bytes):
        """Callback whenever a notified or indicated gatt value is received.

        Args:
            peripheral: The BLE peripheral that generated the notification.
            characteristic: The GATT characteristic that was notified
            value: The raw notified value.
        """

    def on_connect(self, peripheral: BLEPeripheral):
        """Callback when a connection was successful.

        This callback is invoked exactly once for each connection and will happen
        before any other notifications about the device are received.

        Args:
            peripheral: The BLE peripheral that was just successfully connected.
        """

    def on_disconnect(self, peripheral: BLEPeripheral, expected: bool):
        """Callback when a perihperal disconnected.

        This callback is generated exactly once for each connection.  It will
        only be generated if ``on_connect`` has first been called.

        If the disconnection is due to the user calling ``disconnect()`` on the
        central, then the ``expected`` value will be true indicating that the
        disconnection was due to user action.  Otherwise, expected will be False,
        indicating that a setting, communication or timeout error occurred.

        Args:
            peripheral: The BLE peripheral that was just successfully connected.
            expected: Whether the disconnection was the expected result of a
                disconnect operation.
        """


class EmptyPeripheralDelegate:
    """An empty peripheral delegate that performs no actions."""

    def on_notification(self, peripheral: BLEPeripheral, characteristic: GattCharacteristic, value: bytes):
        """Callback whenever a notified or indicated gatt value is received."""

    def on_connect(self, peripheral: BLEPeripheral):
        """Callback when a connection was successful."""

    def on_disconnect(self, peripheral: BLEPeripheral, expected: bool):
        """Callback when a perihperal disconnected."""
