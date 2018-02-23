from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.exceptions import ArgumentError

class FlashBoardStep (object):
    """A Recipe Step used to flash firmware directly

    Currentlly only supports using jlink to flash. Meant to bootstrap firmware

    Args:
        addresses (list[int]): List of slot addresses to check against
        names     (list[str]): List of tile names to check against
        versions  (list[str]): List of tile versions to check against.
    """
    def __init__(self, args):
        if(args.get('file') is None):
            raise ArgumentError("FlashBoardStep Parameter Missing", parameter_name='file')
        if(args.get('port') is None):
            raise ArgumentError("FlashBoardStep Parameter Missing", parameter_name='port')

        if not args['port'].startswith('jlink'):
            raise ArgumentError("FlashBoardStep is currently only possible through jlink", invalid_port = args['port'])

        self._file = args['file']
        self._port = args['port']

    def run(self):
        with HardwareManager(port=self._port) as hw:
            debug = hw.debug()
            debug.flash(self._file)