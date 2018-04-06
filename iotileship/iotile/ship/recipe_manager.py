from __future__ import (unicode_literals, print_function, absolute_import)
import os
import pkg_resources
from iotile.ship.recipe import RecipeObject
from iotile.ship.exceptions import RecipeNotFoundError


class RecipeManager(object):
    """A class that maintains a list of installed recipes and recipe actions.

    It allows fetching recipes by name and auotmatically building RecipeObjects
    from textual descriptions.

    The RecipeManager maintains a dictionary of RecipeAction objects that it
    compiles from all installed iotile packages. It passes this dictionary to
    any Recipe that is created from it so the recipe can find any recipe
    actions that it needs.

    The RecipeManager finds RecipeActions by looking for plugins that
    are registered with pkg_resources.
    """
    def __init__(self):

        self._recipe_actions = {}
        self._recipe_resources = {}
        self._recipes = {}

        for entry in pkg_resources.iter_entry_points('iotile.recipe_action'):
            action = entry.load()
            self._recipe_actions[entry.name] = action

        for entry in pkg_resources.iter_entry_points('iotile.recipe_resource'):
            resource = entry.load()
            self._recipe_resources[entry.name] = resource

    def is_valid_action(self, name):
        """Check if a name describes a valid action.

        Args:
            name (str): The name of the action to check

        Returns:
            bool: Whether the action is known and valid.
        """

        return self._recipe_actions.get(name, None) is not None

    def is_valid_recipe(self, recipe_name):
        """Check if a recipe is known and valid.

        Args:
            name (str): The name of the recipe to check

        Returns:
            bool: Whether the recipe is known and valid.
        """

        return self._recipes.get(recipe_name, None) is not None

    def add_recipe_folder(self, recipe_folder, whitelist=None):
        """Add all recipes inside a folder to this RecipeManager with an optional whitelist.

        Args:
            recipe_folder (str): The path to the folder of recipes to add.
            whitelist (list): Only include files whose os.basename() matches something
                on the whitelist
        """

        if whitelist is not None:
            whitelist = set(whitelist)

        if recipe_folder == '':
            recipe_folder = '.'

        for yaml_file in [x for x in os.listdir(recipe_folder) if x.endswith('.yaml')]:
            if whitelist is not None and yaml_file not in whitelist:
                continue

            recipe = RecipeObject.FromFile(os.path.join(recipe_folder, yaml_file), self._recipe_actions, self._recipe_resources)
            self._recipes[recipe.name] = recipe

        for ship_file in [x for x in os.listdir(recipe_folder) if x.endswith('.ship')]:
            if whitelist is not None and ship_file not in whitelist:
                continue

            recipe = RecipeObject.FromArchive(os.path.join(recipe_folder, ship_file), self._recipe_actions, self._recipe_resources)
            self._recipes[recipe.name] = recipe

    def get_recipe(self, recipe_name):
        """Get a recipe by name.

        Args:
            recipe_name (str): The name of the recipe to fetch. Can be either the
                yaml file name or the name of the recipe.
        """
        if recipe_name.endswith('.yaml'):
            recipe = self._recipes.get(RecipeObject.FromFile(recipe_name, self._recipe_actions, self._recipe_resources).name)
        else:
            recipe = self._recipes.get(recipe_name)
        if recipe is None:
            raise RecipeNotFoundError("Could not find recipe", recipe_name=recipe_name, known_recipes=[x for x in self._recipes.keys()])

        return recipe
