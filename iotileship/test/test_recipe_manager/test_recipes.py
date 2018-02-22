import pytest
import os
import time

from iotile.ship.recipe import RecipeObject
from iotile.ship.recipe_manager import RecipeManager
from iotile.ship.exceptions import RecipeVariableNotPassed

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
    assert run_time <= 0.3
    assert run_time >= 0.1

def test_replace_yaml(get_rm):
    rm = get_rm
    recipe = rm.get_recipe('test_replace_recipe')
    variables = {"custom_wait_time": 1}

    start_time = time.time()
    recipe.run(variables)
    run_time = time.time()-start_time

    assert run_time <= 1.1
    assert run_time >= 0.9

def test_replace_yaml_fail(get_rm):
    #Should fail if no variables are passed
    rm = get_rm
    recipe = rm.get_recipe('test_replace_recipe')
    with pytest.raises(RecipeVariableNotPassed):
        recipe.run()

def test_snippet(get_rm):
    rm = get_rm
    recipe = rm.get_recipe('test_snippet')
    recipe.run()