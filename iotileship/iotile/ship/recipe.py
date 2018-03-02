from __future__ import (unicode_literals, print_function, absolute_import)
import time
from builtins import str
from string import Template
from future.utils import viewitems
from iotile.core.exceptions import ArgumentError
from iotile.ship.exceptions import RecipeFileInvalid, UnknownRecipeActionType, RecipeVariableNotPassed

class RecipeObject(object):
    """An object representing a fixed set of processing steps.

    RecipeObjects are used to create and run production operations
    that need to be controlled and repeatable with no room for error.

    Args:
        name (str): The name of the recipe
        description (str): A textual description of what the recipe
            does.
        steps (list of (RecipeActionObject-like, dict)): A list of steps that
            will be performed every time the recipe is executed. The execution
            will proceed in two steps, first all the steps will be combined with
            their dictionary of parameters and verified.  Then each step will
            be executed in order.
    """

    def __init__(self, name, description=None, steps=None):
        if steps is None:
            steps = []

        self._steps = steps
        self.name = name
        self.description = description

    @classmethod
    def FromFile(cls, path, actions_dict, file_format="yaml"):
        """Create a RecipeObject from a file.

        The file should be a specially constructed yaml file
        that describes the recipe as well as the actions that it performs.

        Args:
            path (str): The path to the recipe file that we wish to load
            actions_dict (dict): A dictionary of named RecipeActionObject
                types that is used to look up all of the steps listed in
                the recipe file.
            file_format (str): The file format of the recipe file.  Currently
                we only support yaml.
        """

        cls._actions_dict = actions_dict

        format_map = {
            "yaml": cls._process_yaml,
        }
        format_handler = format_map.get(file_format)

        if format_handler is None:
            raise ArgumentError("Unknown file format or file extension", file_format=file_format, \
                known_formats=[x for x in format_map if format_map[x] is not None])
        recipe_info = cls._process_yaml(path)

        name = recipe_info.get('name')
        description = recipe_info.get('description')

        if name is None or description is None:
            raise RecipeFileInvalid("Recipe file must contain a name and description", path=path, \
                name=name, description=description)

        steps = []
        for i, action in enumerate(recipe_info.get('actions', [])):
            action_name = action.get('name')
            if action_name is None:
                raise RecipeFileInvalid("Action is missing required name parameter", \
                    parameters=action, path=path)

            action_class = actions_dict.get(action_name)
            if action_class is None:
                raise UnknownRecipeActionType("Unknown step specified in recipe", \
                    action=action_name, step=i + 1, path=path)

            remaining_params = {x: y for x, y in viewitems(action) if x != 'name'}
            step = (action_class, remaining_params)
            steps.append(step)

        return RecipeObject(name, description, steps)

    @classmethod
    def _process_yaml(cls, yamlfile):
        import yaml
        with open(yamlfile, 'rb') as f:
            info = yaml.load(f)
            return info

    def _complete_parameters(self, param, variables):
        """Replace any parameters passed as {} in the yaml file with the
        variable names that are passed in

        Only strings, lists of strings, and dictionaries of strings can have
        replaceable values at the moment
        """
        if isinstance(param, list):
            new_param = list(param)
            for i in range(len(new_param)):
                new_param[i] = self._complete_parameters(new_param[i], variables)
            return new_param
        elif isinstance(param, dict):
            new_param = dict(param)
            for key, value in new_param.items():
                new_param[key] = self._complete_parameters(value, variables)
            return new_param
        else:
            try:
                return Template(param).substitute(variables)
            except TypeError, e:
                return param
            except KeyError, e:
                raise RecipeVariableNotPassed("Variable undefined, need to pass in \
                    through 'variables'", undefined_variable=e.message)

    def prepare(self, variables):
        """Initialize all steps in this recipe using their parameters.

        Args:
            variables (dict): A dictionary of global variable definitions
                that may be used to replace or augment the parameters given
                to each step.

        Returns:
            list of RecipeActionObject like instances: The list of instantiated
                steps that can be used to execute this recipe.
        """
        initialized_steps = []
        if variables is None:
            variables = dict()
        for step, params in self._steps:
            new_params = self._complete_parameters(params, variables)
            initialized_steps.append(step(new_params))
        return initialized_steps

    def run(self, variables=None):
        """Initialize and run this recipe."""
        initialized_steps = self.prepare(variables)
        for i, step in enumerate(initialized_steps):
            start_time = time.time()
            print("===> Step %d: %s\t Description: %s" % (i+1, self._steps[i][0].__name__, \
                self._steps[i][1].get('description', '')))
            out = step.run()
            print("======> Time Elapsed: %.2f seconds" % (time.time()-start_time))
            if out is not None:
                print(out[1])

    def __str__(self):
        output_string = "========================================\n"
        output_string += "Recipe: \t%s\n" % (self.name)
        output_string += "Desciption: \t%s\n" % (self.description)
        output_string += "========================================\n"
        for i, step in enumerate(self._steps):
            output_string += "Step %d: %s\t Description: %s\n " % \
            (i+1, step[0].__name__, step[1].get('description', ''))
        return output_string