"""A generic api for interacting with ble adapters."""

import abc
from typing import Optional
from uuid import UUID
from .scan_delegate import BLEScanDelegate
from .peripheral import BLEPeripheral
from .peripheral_delegate import BLEPeripheralDelegate
from .state import BLECentralState

class AbstractBLECentral(abc.ABC):
    """Abstract specification for how BLE central hardware drivers expose their functionality.

    All operations that can be performed on a BLE central will be exposed via
    these coroutines. There is no standard specification of how the central
    object should be created since this may vary widely.

    BLE Centrals are devices that are capable of scanning for perihperals and
    connecting to them.  They are the active participant in initiating BLE
    operations.
    """

    @abc.abstractmethod
    async def start(self):
        """Start this ble central.

        This method must be called before any other methods may be called. The
        central may perform any necessary processing that is needed before it
        can succesfully respond to commands.
        """

    @abc.abstractmethod
    async def stop(self):
        """Stop this ble central.

        This method must be called before disposing of the BLE central so that
        any internal resources that were reserved may be freed.
        """

    @abc.abstractmethod
    async def connect(self, conn_string: str, delegate: Optional[BLEPeripheralDelegate] = None) -> BLEPeripheral:
        """Connect to a peripheral device.

        This method should perform a combined BLE connect and gatt table probe
        operations. Depending on the underlying central hardware, those
        operations may already be fused together, or a sequence of operations
        may need to be performed inside the implemenation of this method
        before returning a BLEPeripheral subclass that has a complete GATT
        table.

        The connection string used should exactly match a connection string
        received as part of a previous advertisement packet.  If the user
        knows the connection string format for a given BLE central
        implementation, they may construct it explicitly to indicate what
        device they wish to connect to.

        This operation does not natively timeout and should be explicitly
        canceled by the user if it takes too long to connect to the device
        they wish to reach.
        """

    @abc.abstractmethod
    async def disconnect(self, peripheral: BLEPeripheral):
        """Disconnect from a connected peripheral device."""

    @abc.abstractmethod
    async def set_notifications(self, peripheral: BLEPeripheral, characteristic: UUID,
                                enabled: bool, kind: str = 'notify'):
        """Enable or disable notifications/indications on a characteristic.

        This method allows you to control the notification status on any GATT
        characteristic that supports either notifications or indications.
        """

    @abc.abstractmethod
    async def write(self, peripheral: BLEPeripheral, characteristic: UUID,
                    value: bytes, with_response: bool):
        """Write the value of a characteristic.

        You can specify whether the write is acknowledged or unacknowledged.
        Unacknowledged writes may fail with QueueFullError if there is not
        space inside the host controller to hold the write until the next
        connection event.  This error is not fatal and indicates that the
        caller should backoff and try again later.
        """

    @abc.abstractmethod
    async def read(self, peripheral: BLEPeripheral, characteristic: UUID):
        """Read the current value of a characteristic."""

    @abc.abstractmethod
    async def request_scan(self, tag: str, active: bool, delegate: BLEScanDelegate = None):
        """Request that the BLE Central scan for ble devices.

        Many different users of a single ble central could request that
        scanning be performed. As long as at least one request is pending, the
        BLE central should scan whenever it can.  Note that different BLE
        central implementations may have limitations that do not permit
        scanning during certain operations like connecting.
        """

    @abc.abstractmethod
    async def release_scan(self, tag: str):
        """Release a previous scan request.

        If scan information is no longer needed, this method may be called to
        stop receiving advertisements.  Callbacks on the corresponding scan
        delegate will immediately cease and the BLE central should stop
        scanning as soon as it is able to if there are no other active scan
        requesters.
        """

    @abc.abstractmethod
    async def state(self) -> BLECentralState:
        """Return the current state of the BLE central.

        This method is designed to allow the user to discover runtime features
        and limitations of the central that may be important to keep in mind
        as it uses it.

        Specific BLE central classes may return subclases of the base
        BLECentralState in order to expose more information that is
        nonstandard, however they must all report at least the minimum
        information specified in BLECentralState.
        """
