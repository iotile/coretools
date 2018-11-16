"""A virtual tile that ensapsulates resuable behavior."""

from future.utils import itervalues
import os
import imp
import inspect
import pkg_resources
from iotile.core.exceptions import ExternalError, ArgumentError
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

        for entry in pkg_resources.iter_entry_points("iotile.virtual_tile", name):
            obj = entry.load()
            if not issubclass(obj, VirtualTile):
                raise ExternalError("External virtual tile could not be loaded because it does not inherit from VirtualTile")

            return obj

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

        search_dir, filename = os.path.split(script_path)
        if search_dir == '':
            search_dir = './'

        if filename == '' or not os.path.exists(script_path):
            raise ArgumentError("Could not find script to load virtual tile", path=script_path)

        module_name, ext = os.path.splitext(filename)
        if ext != '.py':
            raise ArgumentError("Script did not end with .py", filename=filename)

        try:
            file_obj = None
            file_obj, pathname, desc = imp.find_module(module_name, [search_dir])
            mod = imp.load_module(module_name, file_obj, pathname, desc)
        finally:
            if file_obj is not None:
                file_obj.close()

        devs = [x for x in itervalues(mod.__dict__) if inspect.isclass(x) and issubclass(x, VirtualTile) and x != VirtualTile]
        if len(devs) == 0:
            raise ArgumentError("No VirtualTiles subclasses were defined in script", path=script_path)
        elif len(devs) > 1:
            raise ArgumentError("More than one VirtualTiles subclass was defined in script", path=script_path, tiles=devs)

        return devs[0]

    @tile_rpc(0x0004, "", "H6sBBBB")
    def tile_status(self):
        """Required status RPC that allows matching a proxy object with a tile."""

        status = (1 << 1) | (1 << 0)  # Configured and running, not currently used but required for compat with physical tiles
        return [0xFFFF, self.name, 1, 0, 0, status]
