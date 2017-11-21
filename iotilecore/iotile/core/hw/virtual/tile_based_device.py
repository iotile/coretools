"""A VirtualDevice composed of various tiles.

The device handles RPCs by dispatching them to tiles configured using a config dictionary.
"""

from .virtualdevice import VirtualIOTileDevice
from .virtualtile import VirtualTile


class TileBasedVirtualDevice(VirtualIOTileDevice):
    """A VirtualDevice composed of one or more tiles.

    Args:
        args (dict): A dictionary that lists the tiles that
            should be loaded to create this virtual device.
    """

    def __init__(self, args):
        iotile_id = args.get('iotile_id')

        if isinstance(iotile_id, (basestring, unicode)):
            iotile_id = int(iotile_id, 16)

        tiles = args.get('tiles', [])
        name = args.get('name', "No Name")

        super(TileBasedVirtualDevice, self).__init__(iotile_id, name)

        for desc in tiles:
            name = desc['name']
            address = desc['address']

            args = desc.get('args', {})

            tile_type = VirtualTile.FindByName(name)
            tile = tile_type(address, args, device=self)

            self.add_tile(address, tile)

    def start(self, channel):
        """Start running this virtual device including any necessary worker threads.

        Args:
            channel (IOTilePushChannel): the channel with a stream and trace
                routine for streaming and tracing data through a VirtualInterface
        """

        super(TileBasedVirtualDevice, self).start(channel)

        for tile in self._tiles.itervalues():
            tile.start(channel=channel)

    def stop(self):
        """Stop running this virtual device including any worker threads."""

        for tile in self._tiles.itervalues():
            tile.signal_stop()

        for tile in self._tiles.itervalues():
            tile.wait_stopped()

        super(TileBasedVirtualDevice, self).stop()
