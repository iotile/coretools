"""Generic BLE Central Adapter State."""

from typing import List, Iterable, Optional
from .peripheral import BLEPeripheral

class BLECentralState:
    """Generic data that must be returned by any BLE Central driver.

    This state is defined to contain the minimum amount of information that
    must be queryable about a give BLE central in order to permit the creation
    of generic BLE operations on top of it in a portable way.

    Only the minimum amount of state should be included here since all
    centrals must provide at least this.  Centrals are free to subclass this
    class and provide additional information as long as they cover the minimum.

    Args:
        max_connections: The maximum number of simultaneous peripheral connections
            that can be handled.  This must be a conservative estimate if the
            actual number is not known since it will be used to determine how many
            parallel connections to allow.
        connections: A list of all currently connected peripherals.  This information
            must be reliable even if the connections were existent when the adapter
            was first opened.
    """
    def __init__(self, max_connections: int = 1, connections: Optional[Iterable[BLEPeripheral]] = None):
        self.max_connections = max_connections

        if connections is None:
            connections = []

        self.known_connections = list(connections)  # type: List[BLEPeripheral]
