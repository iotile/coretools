import pkg_resources
from iotile.ship.recipe import RecipeObject

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
        return self._recipes.get(recipe, None) is not None

    def add_recipe_folder(self, recipe_folder):
        pass

    def get_recipe(self, recipe_name):
        return self._recipes