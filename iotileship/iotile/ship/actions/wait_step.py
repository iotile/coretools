from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str
import time

class WaitStep (object):
    def __init__(self, args):
        self._seconds = args['seconds']

    def run(self):
        time.sleep(self._seconds)
