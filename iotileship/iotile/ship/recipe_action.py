from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str

from iotile.core.exceptions import *

class RecipeActionObject (object):
    """
    A RecipeActionObject is an object that represents a single step in a recipe

    RecipeActionObject can be linked together into Recipes to perform
    complex operations.
    """

    def __init__(self, args):
        pass

    def run(self, context, progress):
        """Runs the Recipe Action

        Args:
            context - currently unused
            progress - function handler with the format func(done, total)

        """
        raise InternalError("_run() called that did not override the default empty transformation", object=self)
