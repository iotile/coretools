from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str
from iotile.core.hw.hwmanager import HardwareManager
from iotile.ship.exceptions import RecipeActionMissingParameter

class SetUUIDStep (object):
    def __init__(self, args):
        if(args.get('uuid') is None):
            raise RecipeActionMissingParameter("PromptStep Parameter Missing", parameter_name='file')
        if(args.get('port') is None):
            raise RecipeActionMissingParameter("PromptStep Parameter Missing", parameter_name='port')

        self._uuid = args['uuid']
        self._port = args['port']

    def run(self):
        with HardwareManager(port=self._port) as hw:
            debug = hw.debug()
            debug.flash(self._file)