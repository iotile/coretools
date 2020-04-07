"""A generic api for interacting with ble adapters."""

from uuid import UUID
from typing import Optional
from typing_extensions import Protocol
from iotile.core.utilities.async_tools import OperationManager
from .peripheral import BLEPeripheral
from .state import BLECentralState
from ..interface import messages


class AbstractBLECentral(Protocol):
    """Abstract specification for how BLE central hardware drivers expose their functionality.

    All operations that can be performed on a BLE central will be exposed via
    these coroutines. There is no standard specification of how the central
    object should be created since this may vary widely.

    BLE Centrals are devices that are capable of scanning for peripherals and
    connecting to them.  They are the active participant in initiating BLE
    operations.
    """

    @property
    def events(self) -> OperationManager[messages.BluetoothEvent]:
        """All bluetooth messages are dispatched through this operation manager."""

    async def start(self):
        """Start this ble central.

        This method must be called before any other methods may be called. The
        central may perform any necessary processing that is needed before it
        can succesfully respond to commands.
        """

    async def stop(self):
        """Stop this ble central.

        This method must be called before disposing of the BLE central so that
        any internal resources that were reserved may be freed.
        """

    async def connect(self, conn_string: str) -> BLEPeripheral:
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

    async def disconnect(self, conn_string: str):
        """Disconnect from a connected peripheral device."""

    async def manage_subscription(self, conn_string: str, characteristic: UUID,
                                  enabled: bool, acknowledged: bool = False):
        """Enable or disable notifications/indications on a characteristic.

        This method allows you to control the notification status on any GATT
        characteristic that supports either notifications or indications.

        If you pass acknowledged = False, the default, then notifications will
        be enabled/disabled.

        If you pass acknowledged = True, then indications will be enabled/disabled.
        """

    async def advanced_operation(self, operation: str, conn_string: Optional[str], *args, **kwargs):
        """Start or respond to an advanced bluetooth operation.

        This allow for performing advanced optionations that are infrequently used so
        they don't need their own named API methods.  The kinds of things you can
        potentially perform here are:

         - acknowledging receipt of an indication
         - configuring oob keying material for encrypting a bluetooth link
        """

    async def write(self, conn_string: str, characteristic: UUID,
                    value: bytes, with_response: bool = False):
        """Write the value of a characteristic.

        You can specify whether the write is acknowledged or unacknowledged.
        Unacknowledged writes may fail with QueueFullError if there is not
        space inside the host controller to hold the write until the next
        connection event.  This error is not fatal and indicates that the
        caller should backoff and try again later.
        """

    async def read(self, conn_string: str, characteristic: UUID):
        """Read the current value of a characteristic."""

    async def request_scan(self, tag: str, active: bool):
        """Request that the BLE Central scan for ble devices.

        Many different users of a single ble central could request that
        scanning be performed. As long as at least one request is pending, the
        BLE central should scan whenever it can.  Note that different BLE
        central implementations may have limitations that do not permit
        scanning during certain operations like connecting.
        """

    async def release_scan(self, tag: str):
        """Release a previous scan request.

        If scan information is no longer needed, this method may be called to
        stop receiving advertisements.  Callbacks on the corresponding scan
        delegate will immediately cease and the BLE central should stop
        scanning as soon as it is able to if there are no other active scan
        requesters.
        """

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
