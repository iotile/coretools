import pytest
import os
from iotile.ship.recipe_manager import RecipeManager

def test_recipe_manager_import():

    rm = RecipeManager()

    assert rm.is_valid_action('WaitStep')
    assert rm.is_valid_action('PromptStep')

    rm.add_recipe_folder(os.path.join(os.path.dirname(__file__), 'test_recipes'))  # includes recipe.yaml

    assert rm.is_valid_recipe('test_basic_yaml')

    
