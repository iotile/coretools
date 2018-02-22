from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str
from iotile.ship.exceptions import RecipeActionMissingParameter, UnexpectedOutput
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.exceptions import ArgumentError

from subprocess import PIPE, STDOUT, Popen


class PipeSnippetStep (object):
    """A Recipe Step used to pipe snippets into a context.

    Currently, this step doesn't store any information typed into 
    the input. It currently stalls the recipe from running before it
    progresses. Take a look a test/test_recipe_manager/test_recipes/test_snippet.yaml
    for an example usage

    Args:
        context (str): The starting context of which commands are to be performed
        commands (list[str]): List of commands to pipe into context
        expected (list[str]): List of expected piped outputs. Ignores the current context name.
    """
    def __init__(self, args):
        if(args.get('context') is None):
            raise RecipeActionMissingParameter("PromptStep Parameter Missing", parameter_name='context')
        if(args.get('commands') is None):
            raise RecipeActionMissingParameter("PromptStep Parameter Missing", parameter_name='commands')


        self._context = args['context']
        self._commands = args['commands']
        self._expect = args.get('expect',None)

        if self._expect is not None:
            if(len(self._expect) != len(self._commands)):
                raise ArgumentError("Length of expect must match length of commands", parameter_name='commands')

    def run(self):
        p = Popen(self._context,stdout=PIPE, stdin=PIPE, stderr=STDOUT)
        outputs = p.communicate(input = '\r\n'.join(self._commands))[0].split('\r\n')

        if self._expect is not None:
            for i in range(len(self._commands)):
                expected_output = self._expect[i]
                if expected_output is None:
                    continue

                raw_outputs     = outputs[i].split(') ',1)
                output          = raw_outputs[1] if len(raw_outputs) == 2 else ""
                
                if output != expected_output:
                    raise ArgumentError("Unexpected output", command = self._commands[i], expected = expected_output, actual = output)


