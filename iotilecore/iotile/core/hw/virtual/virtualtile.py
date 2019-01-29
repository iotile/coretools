"""A virtual tile that ensapsulates resuable behavior."""

from iotile.core.exceptions import ArgumentError
from iotile.core.dev import ComponentRegistry
from .base_runnable import BaseRunnable
from .common_types import tile_rpc, RPCDispatcher


class VirtualTile(BaseRunnable, RPCDispatcher):
    """A virtual tile.

    Tiles have their own RPC based API and can run background
    threads to do periodic work.

    Args:
        address (int): The address of this tile in the VirtualIOTIleDevice
            that contains it
        name (str): The 6 character name that should be returned when this
            tile is asked for its status to allow matching it with a proxy
            object.
        device (TileBasedVirtualDevice) : optional, device on which this tile is running
    """

    def __init__(self, address, name, device=None):
        super(VirtualTile, self).__init__()

        self.address = address
        self.name = self._check_convert_name(name)

    @classmethod
    def _check_convert_name(cls, name):
        if not isinstance(name, bytes):
            name = name.encode('utf-8')
        if len(name) < 6:
            name += b' '*(6 - len(name))
        elif len(name) > 6:
            raise ArgumentError("Virtual tile name is too long, it must be 6 or fewer characters")

        return name

    def start(self, channel=None):
        """Start any background workers on this tile."""
        self.start_workers()

    def stop(self):
        """Stop any background workers on this tile."""
        self.stop_workers()

    def signal_stop(self):
        """Asynchronously signal that all workers should stop."""
        self.stop_workers_async()

    def wait_stopped(self):
        """Wait for all workers to stop."""
        self.wait_workers_stopped()

    @classmethod
    def FindByName(cls, name):
        """Find an installed VirtualTile by name.

        This function searches for installed virtual tiles
        using the pkg_resources entry_point `iotile.virtual_tile`.

        If name is a path ending in .py, it is assumed to point to
        a module on disk and loaded directly rather than using
        pkg_resources.

        Args:
            name (str): The name of the tile to search
                for.

        Returns:
            VirtualTile class: A virtual tile subclass that can be
                instantiated to create a virtual tile.
        """

        if name.endswith('.py'):
            return cls.LoadFromFile(name)

        reg = ComponentRegistry()
        for _name, tile in reg.load_extensions('iotile.virtual_tile', name_filter=name, class_filter=VirtualTile):
            return tile

        raise ArgumentError("VirtualTile could not be found by name", name=name)

    @classmethod
    def LoadFromFile(cls, script_path):
        """Import a virtual tile from a file rather than an installed module

        script_path must point to a python file ending in .py that contains exactly one
        VirtualTile class definition.  That class is loaded and executed as if it
        were installed.

        To facilitate development, if there is a proxy object defined in the same
        file, it is also added to the HardwareManager proxy registry so that it
        can be found and used with the device.

        Args:
            script_path (string): The path to the script to load

        Returns:
            VirtualTile: A subclass of VirtualTile that was loaded from script_path
        """

        _name, dev = ComponentRegistry().load_extension(script_path, class_filter=VirtualTile, unique=True)
        return dev

    @tile_rpc(0x0004, "", "H6sBBBB")
    def tile_status(self):
        """Required status RPC that allows matching a proxy object with a tile."""

        status = (1 << 1) | (1 << 0)  # Configured and running, not currently used but required for compat with physical tiles
        return [0xFFFF, self.name, 1, 0, 0, status]
