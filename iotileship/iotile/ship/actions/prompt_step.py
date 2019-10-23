"""PromptStep. Currently used to stall the recipe prior to running"""
from iotile.ship.exceptions import RecipeActionMissingParameter


class PromptStep:  # pylint:disable=too-few-public-methods; all Steps have one "run" function
    """A Recipe Step used to prompt the user for input.

    Currently, this step doesn't store any information typed into
    the input. It currently stalls the recipe from running before it
    progresses

    Args:
        message (str): The message that will be displayed
    """
    def __init__(self, args):
        if args.get('message') is None:
            raise RecipeActionMissingParameter("PromptStep Parameter Missing", parameter_name='message')

        self._message = args['message']

    def run(self):
        """Get user input to exit the pause"""
        input(str(self._message))
