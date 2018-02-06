import os

from future.utils import viewitems

from iotile.core.exceptions import ArgumentError
from iotile.ship.exceptions import *

class RecipeObject(object):
    """
    An object containing the pipeline for processing recipes

    An entire pipeline configuration can be serialized to/from a json file to allow
    for easy setup/version control of pcb pipelines.
    """

    def __init__(self, name, description=None, steps=None):
        if steps is None:
            steps = []

        self._steps = steps
        self.name = name
        self.description = description

    @classmethod
    def FromFile(cls, path, actions_dict, file_format="yaml"):
        cls._actions_dict = actions_dict

        format_map = {
            "json": cls._process_json,
            "yaml": cls._process_yaml,
        }

        format_handler = format_map.get(file_format)
        if format_handler is None:
            raise ArgumentError("Unknown file format or file extension", file_format=file_format, known_formats=[x for x in format_map if format_map[x] is not None])
        recipe_info = format_handler(path)

        name = recipe_info.get('name')
        description = recipe_info.get('description')

        if name is None or description is None:
            raise RecipeFileInvalid("Recipe file must contain a name and description", path=path, name=name, description=description)

        steps = []
        for i, action in enumerate(recipe_info.get('actions', [])):
            action_name = action.get('name')
            if action_name is None:
                raise RecipeFileInvalid("Action is missing required name parameter", parameters=action, path=path)

            action_class = actions_dict.get(action_name)
            if action_class is None:
                raise UnknownRecipeActionType("Unknown step specified in recipe", action=action_name, step=i + 1, path=path)

            remaining_params = {x: y for x, y in viewitems(action) if x != 'name'}
            step = (action_class, remaining_params)
            steps.append(step)

        return RecipeObject(name, description, steps)

    @classmethod
    def _process_json(cls, jsonfile):
        import json
        with open(jsonfile, 'rb') as f:
            info = json.load(f)
            return info

    @classmethod
    def _process_yaml(cls, yamlfile):
        import yaml
        with open(yamlfile, 'rb') as f:
            info = yaml.load(f)
            return info

    def prepare(self, variables=None):
        return [step(params) for step, params in self._steps]

    def run(self):
        initialized_steps = self.prepare()

        for step in initialized_steps:
            step.run()
