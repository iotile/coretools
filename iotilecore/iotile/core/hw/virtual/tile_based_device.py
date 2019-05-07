"""A VirtualDevice composed of various tiles.

The device handles RPCs by dispatching them to tiles configured using a config dictionary.
"""

from iotile.core.exceptions import ArgumentError
from ..exceptions import RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from .virtualdevice_standard import StandardVirtualDevice
from .virtualtile import VirtualTile

class TileBasedVirtualDevice(StandardVirtualDevice):
    """A VirtualDevice composed of one or more tiles.

    Args:
        args (dict): A dictionary that lists the tiles that
            should be loaded to create this virtual device.
    """

    def __init__(self, args):
        iotile_id = args.get('iotile_id')

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
