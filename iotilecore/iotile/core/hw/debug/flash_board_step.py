from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.exceptions import ArgumentError

class FlashBoardStep (object):
    """A Recipe Step used to flash firmware directly

    Currently only supports using jlink to flash. Meant to bootstrap firmware

    Args:
        file (str): Firmware file name to flash
        port (str): Port used. Currently only allows jlink port connections.
        debug_string (str): Optional connection string for debug
    """
    FILES = ['file']

    def __init__(self, args):
        if 'file' not in args:
            raise ArgumentError("FlashBoardStep required parameters missing", required=["file"], args=args)
        if 'port' not in args:
            raise ArgumentError("FlashBoardStep Parameter Missing", parameter_name='port', args=args)

        if not args['port'].startswith('jlink'):
            raise ArgumentError("FlashBoardStep is currently only possible through jlink", invalid_port=args['port'])

        self._file = args['file']
        self._port = args['port']
        self._debug_string = args.get('debug_string')

    def run(self):
        with HardwareManager(port=self._port) as hw:
            debug = hw.debug(self._debug_string)
            debug.flash(self._file)