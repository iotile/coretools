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
        if self._tile == "controller":
            rb.reflash_controller(self._file)
        else:
            rb.reflash_tile(self._tile, self._file)

class SetFirmwareTagStep:
    """A Recipe Step to set the firmware os or app tags

    This function requires a shared hardware manager resource to be setup
    containing a connected device that we can send the script to.

    Args:
        tag_name (str): Tag name ('os' or 'app')
        tag (int): OS tag
        version (str): OS version
    """
    REQUIRED_RESOURCES = [('connection', 'hardware_manager')]

    def __init__(self, args):
        if 'tag_name' not in args:
            raise ArgumentError("SetFirmwareTagStep required parameters missing", required=["tag_name"], args=args)
        if args['tag_name'] not in ['os','app']:
            raise ArgumentError("SetFirmwareTagStep tag name is not valid. Expected 'os' or 'app'.", args=args)
        if 'tag' not in args:
            raise ArgumentError("SetFirmwareTagStep required parameters missing", required=["tag"], args=args)
        if 'version' not in args:
            raise ArgumentError("SetFirmwareTagStep required parameters missing", required=["version"], args=args)

        self._name = args['tag_name']
        self._tag = args['tag']
        self._version = args['version']

    def run(self, resources):
        """Runs the step

        Args:
            resources (dict): A dictionary containing the required resources that
                we needed access to in order to perform this step.
        """
        hwman = resources['connection']
        con = hwman.hwman.controller()
        rb = con.remote_bridge()

        rb.create_script()
        rb.add_setversion_action(self._name, self._tag, self._version)
        rb.send_script()
        rb.wait_script()

class SetUUIDStep:
    """A Recipe Step to set the uuid of a POD 

    This function requires a shared hardware manager resource to be setup
    containing a connected device that we can send the script to.

    Args:
        uuid (int): UUID to set
    """
    REQUIRED_RESOURCES = [('connection', 'hardware_manager')]

    def __init__(self, args):
        if 'uuid' not in args:
            raise ArgumentError("SetUUIDStep required parameters missing", required=["uuid"], args=args)

        self._uuid = args['uuid']

    def run(self, resources):
        """Runs the step

        Args:
            resources (dict): A dictionary containing the required resources that
                we needed access to in order to perform this step.
        """
        hwman = resources['connection']
        con = hwman.hwman.controller()
        rb = con.remote_bridge()

        rb.create_script()
        rb.add_setuuid_action(self._uuid)
        rb.send_script()
        rb.wait_script()


