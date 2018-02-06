import os
from iotile.core.exceptions import ArgumentError
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
        if hasattr(actions, step_type):
            return getattr(actions, step_type)

        raise UnknownRecipeActionType("Unknown stage type specified, cannot create it", name=step_type)


    @classmethod
    def FromFile(cls, path, file_format="yaml"):
        
        format_map = {
            "json": cls._process_json,
            "yaml": cls._process_yaml,
        }

        format_handler = format_map.get(file_format)
        if format_handler is None:
            raise ArgumentError("Unknown file format or file extension", file_format=file_format, known_formats=[x for x in format_map if format_map[x] is not None])
        recipe = format_handler(path)
        return recipe

    @classmethod
    def _process_json(cls, jsonfile):
        import json
        with open(jsonfile, 'rb') as f:
            info = json.load(f)
            recipe = RecipeObject(info['name'], info['description'])
            for action in info['actions']:
                steptype = RecipeObject.CreateStep(action['name'])

                recipe.add_step(steptype(action))
        return recipe

    @classmethod
    def _process_yaml(cls, yamlfile):
        import yaml
        with open(yamlfile, 'rb') as f:
            info = yaml.load(f)
            recipe = RecipeObject(info['name'], info['description'])
            for action in info['actions']:
                steptype = RecipeObject.FindStep(action['name'])

                recipe.add_step(steptype(action))
        return recipe

    def run(self):
        for step in self._steps:
            step.run()

    def add_step(self, step):
        self._steps += [step]