import os
from iotile.core.exceptions import ArgumentError
from iotile.ship.exceptions import *
import actions

class RecipeObject (object):
    """
    An object containing the pipeline for processing recipes
    
    An entire pipeline configuration can be serialized to/from a json file to allow
    for easy setup/version control of pcb pipelines.
    """

    def __init__(self, args):
        self._steps         = []
        self._name          = args.get("name", None)
        self._description   = args.get("description", None)

    @classmethod
    def CreateStep(cls, step_type):
        """
        Create a step by specifying its name
        """
        if cls._actions_dict.get(step_type, None) is not None:
            return cls._actions_dict.get(step_type)

        raise UnknownRecipeActionType("Unknown stage type specified, cannot create it", name=step_type)


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
        
        args = {
            'name': recipe_info['name'],
            'description' : recipe_info['description']
        }
        recipe = RecipeObject(args)
        for action in recipe_info['actions']:
            steptype = RecipeObject.CreateStep(action['name'])
            recipe._add_step(steptype(action))

        return recipe

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

    def _add_step(self, step):
        self._steps += [step]

    def run(self):
        for step in self._steps:
            step.run()

    