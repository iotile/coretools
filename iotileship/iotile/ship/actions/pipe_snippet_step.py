from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str
import shlex
from subprocess import PIPE, STDOUT, Popen
from iotile.ship.exceptions import RecipeActionMissingParameter
from iotile.core.exceptions import ArgumentError
import re

class PipeSnippetStep(object):
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
        if args.get('context') is None:
            raise RecipeActionMissingParameter("PromptStep Parameter Missing", \
                parameter_name='context')
        if args.get('commands') is None:
            raise RecipeActionMissingParameter("PromptStep Parameter Missing", \
                parameter_name='commands')

        self._context = args['context']
        self._commands = args['commands']
        self._expect = args.get('expect', None)

        if self._expect is not None:
            if len(self._expect) != len(self._commands):
                raise ArgumentError("Length of expect must match length of commands", \
                    parameter_name='commands')

    def run(self):
        process = Popen(shlex.split(self._context), stdout=PIPE, stdin=PIPE, stderr=STDOUT)
        out, err = process.communicate(input='\n'.join(self._commands).encode('utf-8'))
        if err is not None:
            raise ArgumentError("Output Errored", errors=err, commands=self._commands)

        out = out.decode('utf-8')

        # The output from each command would be a context string followed by output data.
        #   A context string is a string in parenteses e.g. (GPIOPipelineProxy).  AKA a prompt
        #   The result is after the context string.
        #   There can be carriage returns '\n' between the prompts
        #Split outputs and remove context strings
        out = re.sub(r'\n',' ',out)
        outraw = re.split(r'(\(\w+\))',out)
        outraw.pop(0)
        outputs = []
        for item in outraw:
            if not re.match(r'\(\w+\)', item):
                outputs.append(item.strip())

        return_strings = []

        for i in range(len(self._commands)):
            return_strings += ["Command: %s\nOutput: %s" % (self._commands[i], outputs[i])]
            if self._expect is not None:
                expected_output = self._expect[i]
                if expected_output is not None:
                    if outputs[i] != expected_output:
                        raise ArgumentError("Unexpected output", command=self._commands[i], \
                            expected=expected_output, actual=outputs[i])
        print('\n'.join(return_strings))
