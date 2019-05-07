"""Base class for all virtual tiles."""

from iotile.core.exceptions import ArgumentError
from iotile.core.dev import ComponentRegistry
from .common_types import RPCDispatcher


class BaseVirtualTile(RPCDispatcher):
    """A virtual tile.

    Tiles have their own RPC based API and can run background tasks that
    stream or trace data asynchronously to any user-called RPC by using the
    ``channel`` member.

    Args:
        address (int): The address of this tile in the VirtualIOTIleDevice
            that contains it
    """

    def __init__(self, address):
        super(BaseVirtualTile, self).__init__()

        self.address = address
        self.channel = None

    def start(self, channel=None):
        """Start any activity on this tile.

        Subclasses that have background workers or other activity
        can override this method to start their background work.

        Callers should pass an :class:`VirtualAdapterAsyncChannel` object as
        the channel parameter to allow tiles to stream and trace data.

        Args:
            channel (VirtualAdapterAsyncChannel): An optional channel for
                this tile to send stream and trace data asynchronously
                out of the simulated device.
        """

        self.channel = channel

    def stop(self):
        """Stop any background work on this tile."""

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
        for _name, tile in reg.load_extensions('iotile.virtual_tile', name_filter=name, class_filter=BaseVirtualTile):
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

        _name, dev = ComponentRegistry().load_extension(script_path, class_filter=BaseVirtualTile, unique=True)
        return dev
