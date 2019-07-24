"""A VirtualDevice composed of various tiles.

The device handles RPCs by dispatching them to tiles configured using a config dictionary.
"""
from iotile.core.hw.virtual import tile_rpc
from .virtualdevice_standard import StandardVirtualDevice
from .virtualtile import VirtualTile


class TileBasedVirtualDevice(StandardVirtualDevice):
    """A VirtualDevice composed of one or more tiles.

    Args:
        args (dict): A dictionary that lists the tiles that
            should be loaded to create this virtual device.
        override_controller (bool): Controls whether the virtual controller
            gets added or not. Defaults to false.
    """

    def __init__(self, args):
        iotile_id = args.get('iotile_id')

        override_controller = args.get('override_controller', False)

        con_args = args

        if isinstance(iotile_id, str):
            iotile_id = int(iotile_id, 16)

        super(TileBasedVirtualDevice, self).__init__(iotile_id)

        for desc in args.get('tiles', []):
            name = desc['name']
            address = desc['address']

            args = desc.get('args', {})

            tile_type = VirtualTile.FindByName(name)
            tile = tile_type(address, args, device=self)

            self.add_tile(address, tile)

        # Add a controller tile
        if not override_controller:
            tile = VirtualController(8, con_args, device=self)
            self.add_tile(8, tile)
            tile.tiles = self._tiles
            tile.prep_count()

    def start(self, channel):
        """Start running this virtual device including any necessary worker threads.

        Args:
            channel (IOTilePushChannel): the channel with a stream and trace
                routine for streaming and tracing data through a VirtualInterface
        """

        super(TileBasedVirtualDevice, self).start(channel)

        for tile in self._tiles.values():
            tile.start(channel=channel)

    def stop(self):
        """Stop running this virtual device including any worker threads."""

        for tile in self._tiles.values():
            tile.stop()

        super(TileBasedVirtualDevice, self).stop()


class VirtualController(VirtualTile):
    """A tile based virtual controller. Contains a very limited subset of controller RPCs currently.

    When using it, you should force your program to see it as an 'NRF52 ' proxy, because vircon is
    not an actual proxy object (there are no unique RPCs here outside of the base controller spec).
    The syntax for doing this is something like:

    get 8 -f 'NRF52 '
    (assuming you are connected to the device already).

    To use the RPCs, you should use the test_interface calls for get_info and set_version.
    """

    def __init__(self, address, config, device):

        self.config = config
        super(VirtualController, self).__init__(address, 'vircon')

        self.tile_list = []

    def prep_count(self):
        """Put the actual tile indices in to a list that complies with the count_tiles and describe_tile API"""
        for tile in self.tiles:
            self.tile_list.append(tile)

    @tile_rpc(0x0004, "", "H6sBBBB")
    def status(self):
        """Return a dummy status"""
        return [0xFFFF, "vircon", 1, 0, 0, 1]

    @tile_rpc(0x0002, "", "10s")
    def hardware_version(self):
        """Return the hardware identification string."""
        return [b'virtualcon']

    @tile_rpc(0x2a01, "", "H")
    def count_tiles(self):
        """Count the number of registered tiles including the controller"""
        return [len(self.tile_list)]

    @tile_rpc(0x2a02, "H", "3B6s6BBL")
    def describe_tile(self, index):
        """Describes a tile at the given index

        The information returned is the exact same data as what REGISTER_TILE
        includes as its argument.

        Args:
        - uint16_t: The index of the tile you wish to describe.  Must be less than
            what COUNT_TILES returns.

        Returns:
        - uint8_t: a numerical hardware type identifer for the processor the tile is
            running on.
        - two bytes: (major, minor) API level of the tile fwutive running on this
            tile.  The api version is encoded with the major version as a byte
            followed by the minor version.
        - 6-character string: The tile firmware identifier that is used to match it
            with the correct proxy module by HardwareManager.
        - 3 bytes: (major, minor, patch) version identifier of the application
            firmware running on this tile.
        - 3 bytes: (major, minor, patch) version identifier of the tile executive
            running on this tile.
        - uint8_t: The slot number that refers to the physical location of this tile
            on the board.  It is used to assign the tile a fixed address on the
            TileBus.
        - uint32_t: A unique identifier for this tile, if the tile supports unique
            identifiers.
        """
        tile = self.tiles[self.tile_list[index]]
        return (0, 0, 0, tile.name, 0, 0, 0, 0, 0, 0, self.tile_list[index], 0)
