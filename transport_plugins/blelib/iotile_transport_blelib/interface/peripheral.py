"""Basic peripheral class containing information about a BLE device."""

from typing import Optional
from uuid import UUID
from .gatt import GattTable, GattCharacteristic
from .errors import GattError

class BLEPeripheral:
    """The base class encapsulating all behavior related to a BLE peripheral connection.

    A subclass of BLEPeripheral must be generated and returned by a BLECentral when a
    successful connection is made to a BLE device.  It must be passed back by the
    user whenever they wish to take some action related to the connected device.

    BLECentrals are free to store whatever private information they wish inside their
    subclass.  The only required public information is the gatt table and connection_string
    that are defined in this base class.

    Args:
        conn_string: A string that will uniquely identify this connection for ble
            operations.  This is normally a MAC address or a UUID depending on the
            bluetooth stack.
        table: The probed or cached GATT table from the peripheral.
    """

    def __init__(self, conn_string: str, table: Optional[GattTable]):
        self.connection_string = conn_string
        self.gatt_table = table

    def find_char(self, char: UUID) -> GattCharacteristic:
        """Find a characteristics inside the peripheral's gatt table.

        This function looks up the corresponding characteristic based on the
        provided UUID.

        Args:
            char: The UUID to lookup

        Returns:
            The gatt characteristic

        Raises:
            GattError: The peripheral's Gatt table has not been probed yet
            KeyError: The desired characteristic was not found.
        """

        if self.gatt_table is None:
            raise GattError("Peripheral does not have a probed GATT table", self.connection_string)

        return self.gatt_table.find_char(char)

    def prepare_write(self, char: UUID, new_value: bytes):
        if self.gatt_table is None:
            raise GattError("Peripheral does not have a probed GATT table", self.connection_string)

        found = self.gatt_table.find_char(char)

        found.value.value = new_value
        return found.value.handle
