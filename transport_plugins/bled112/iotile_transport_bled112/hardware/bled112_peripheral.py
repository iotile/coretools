"""BLEPeripheral subclass containing bled112 specific information."""

from iotile_transport_blelib.interface import BLEPeripheral

class BLED112Peripheral(BLEPeripheral):
    def __init__(self, address: str, handle: int, table=None):
        super(BLED112Peripheral, self).__init__(address, table)

        self.conn_handle = handle
