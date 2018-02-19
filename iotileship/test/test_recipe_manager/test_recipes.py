import pytest
import os
import time

from iotile.ship.recipe import RecipeObject
from iotile.ship.recipe_manager import RecipeManager

@pytest.fixture
def get_rm():
    rm = RecipeManager()
    rm.add_recipe_folder(os.path.join(os.path.dirname(__file__), 'test_recipes'))  # includes recipe.yaml
    return rm

def test_basic_yaml(get_rm):
    rm = get_rm
    recipe = rm.get_recipe('test_basic_yaml')

    assert recipe.name == 'test_basic_yaml'
    assert recipe._steps[0][0].__name__ == 'WaitStep'
    
    assert recipe._steps[0][1]['seconds'] == 0.2


    start_time = time.time()
    recipe.run()
    run_time = time.time()-start_time
    assert run_time <  0.4
    assert run_time >= 0.19