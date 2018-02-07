import pytest
import os
import subprocess

from iotile.ship.recipe import RecipeObject
from iotile.ship.actions import *

def test_flash_board_recipe(monkeypatch):

    recipe = RecipeObject.FromFile(os.path.join(os.path.dirname(__file__),"test_flash_board_recipe.json"),file_format='json')
    recipe.run()