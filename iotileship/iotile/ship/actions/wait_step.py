from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str
from iotile.ship.exceptions import RecipeActionMissingParameter
import time

class WaitStep (object):
    def __init__(self, args):
        if(args.get('seconds') is None):
            raise RecipeActionMissingParameter("WaitStep Parameter Missing", parameter_name='seconds')

        self._seconds = args['seconds']

    def run(self):
        time.sleep(self._seconds)
