import pkg_resources
import os, sys
import glob
from iotile.ship.recipe import RecipeObject
from iotile.ship.exceptions import RecipeNotFoundError


class RecipeManager(object):
    """
    RecipeManager

    The RecipeManager maintains a dictionary of RecipeAction objects that it compiles from all installed iotile packages.
    It passes this dictionary to any Recipe that is created from it so the recipe can find any recipe actions that it needs.

    The RecipeManager should find RecipeActions by looking for plugins that are registered with pkg_resources.
    """
    def __init__(self):

        self._recipe_actions = {}
        self._recipes = {}

        for entry in pkg_resources.iter_entry_points('iotile.recipe_action'):
            action = entry.load()
            self._recipe_actions[entry.name] = action

    def is_valid_action(self, name):
        return self._recipe_actions.get(name, None) is not None

    def is_valid_recipe(self, recipe_name):
        return self._recipes.get(recipe_name, None) is not None

    def add_recipe_folder(self, recipe_folder):
        for yaml_file in glob.glob("%s/*.yaml" % recipe_folder):
            recipe = RecipeObject.FromFile(yaml_file, self._recipe_actions)
            self._recipes[recipe.name] = recipe

        for json_file in glob.glob("%s/*.json" % recipe_folder):
            recipe = RecipeObject.FromFile(json_file, self._recipe_actions, file_format='json')
            self._recipes[recipe.name] = recipe



    def get_recipe(self, recipe_name):
        recipe = self._recipes.get(recipe_name)
        if recipe is None:
            raise RecipeNotFoundError("Could not find recipe", recipe_name=recipe_name)
        return self._recipes
