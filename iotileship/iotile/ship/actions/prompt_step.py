from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str
from iotile.ship.exceptions import RecipeActionMissingParameter


class PromptStep (object):
    def __init__(self, args):
        if(args.get('message') is None):
            raise RecipeActionMissingParameter("PromptStep Parameter Missing", parameter_name='message')

        self._message = args['message']

    def run(self):
        raw_input(self._message)
