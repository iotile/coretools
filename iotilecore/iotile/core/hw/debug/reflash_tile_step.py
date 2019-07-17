from iotile.core.exceptions import ArgumentError


class ReflashTileStep:
    """A Recipe Step used to reflash a tile using the remote bridge.

    This function requires a shared hardware manager resource to be setup
    containing a connected device that we can send the script to.

    Args:
        file (str): Firmware file name to flash
        tile (fw_tileselector): Tile to flash
    """
    REQUIRED_RESOURCES = [('connection', 'hardware_manager')]
    FILES = ['file']

    def __init__(self, args):
        if 'file' not in args:
            raise ArgumentError("ReflashTileStep required parameters missing", required=["file"], args=args)
        if 'tile' not in args:
            raise ArgumentError("ReflashTileStep required parameters missing", required=["tile"], args=args)

        self._file = args['file']
        self._tile = args['tile']

    def run(self, resources):
        """Runs the reflash step

        Args:
            resources (dict): A dictionary containing the required resources that
                we needed access to in order to perform this step.
        """
        hwman = resources['connection']
        con = hwman.hwman.controller()
        rb = con.remote_bridge()
        rb.reflash_tile(self._tile, self._file)
