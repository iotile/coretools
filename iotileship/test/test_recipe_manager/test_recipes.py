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

def test_basic_yaml(get_rm, monkeypatch):
    rm = get_rm
    recipe = rm.get_recipe('test_basic_yaml')

    assert recipe.name == 'test_basic_yaml'
    assert recipe._steps[0][0].__name__ == 'PromptStep'
    assert recipe._steps[1][0].__name__ == 'WaitStep'
    
    assert recipe._steps[0][1]['message'] == 'Connect JLink to tile 1'
    assert recipe._steps[1][1]['seconds'] == 2


    start_time = time.time()
    inputs = ['']
    input_generator = (i for i in inputs)
    monkeypatch.setattr('__builtin__.raw_input', lambda prompt: next(input_generator))
    recipe.run()
    assert (time.time()-start_time) <  4.0
    assert (time.time()-start_time) >= 2.0