from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.exceptions import ArgumentError

class FlashBoardStep (object):
    """A Recipe Step used to flash firmware directly
    
    Currently only supports using jlink to flash. Used to bootstrap firmware

    This function requires a shared hardware manager resource to be setup
    containing a connected device that we can send the script to.

    Args:
        file (str): Firmware file name to flash
        debug_string (str): Optional connection string for debug
    """
    REQUIRED_RESOURCES = [('connection', 'hardware_manager')]
    FILES = ['file']

    def __init__(self, args):
        if 'file' not in args:
            raise ArgumentError("FlashBoardStep required parameters missing", required=["file"], args=args)

        self._file = args['file']
        self._debug_string = args.get('debug_string')

    def run(self, resources):
        """Runs the flash step

        Args:
            resources (dict): A dictionary containing the required resources that
                we needed access to in order to perform this step.
        """
        if not resources['connection']._port.startswith('jlink'):
            raise ArgumentError("FlashBoardStep is currently only possible through jlink", invalid_port=args['port'])

        hwman = resources['connection']
        debug = hwman.hwman.debug(self._debug_string)
        debug.flash(self._file)