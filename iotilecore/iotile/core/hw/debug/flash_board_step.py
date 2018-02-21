from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.exceptions import ArgumentError

class FlashBoardStep (object):
    def __init__(self, args):
        if(args.get('file') is None):
            raise ArgumentError("PromptStep Parameter Missing", parameter_name='file')
        if(args.get('port') is None):
            raise ArgumentError("PromptStep Parameter Missing", parameter_name='port')

        if 'jlink' not in args['port'][0:5]:
            raise ArgumentError("FlashBoardStep is currently only possible through jlink", invalid_port = args['port'])

        self._file = args['file']
        self._port = args['port']

    def run(self):
        with HardwareManager(port=self._port) as hw:
            debug = hw.debug()
            debug.flash(self._file)