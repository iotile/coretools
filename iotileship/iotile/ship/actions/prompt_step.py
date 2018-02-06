from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str


class PromptStep (object):
    def __init__(self, args):
        self._message = args['message']

    def run(self):
        raw_input(self._message)
