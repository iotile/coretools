import time
from iotile.ship.exceptions import RecipeActionMissingParameter


class WaitStep:
    """A Recipe Step used to waits a certain amount of time

    WaitStep stops the recipe from running for a set number of seconds

    Args:
        seconds (int): The number of seconds to wait.
    """
    def __init__(self, args):
        if args.get('seconds') is None:
            raise RecipeActionMissingParameter("WaitStep Parameter Missing", \
                parameter_name='seconds')

        self._seconds = args['seconds']

    def run(self):
        time.sleep(float(self._seconds))
