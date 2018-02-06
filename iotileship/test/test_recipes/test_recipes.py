import pytest
import os
import subprocess
import time

from iotile.ship.recipe import RecipeObject
from iotile.ship.actions import *

def test_prompt_step_json(monkeypatch):
    inputs = ['']
    input_generator = (i for i in inputs)
    monkeypatch.setattr('__builtin__.raw_input', lambda prompt: next(input_generator))
    
    recipe = RecipeObject.FromFile(os.path.join(os.path.dirname(__file__),"test_prompt_recipe.json"),file_format='json')
    start_time = time.time()
    recipe.run()

    assert (time.time()-start_time) <  4.0
    assert (time.time()-start_time) >= 2.0


def test_prompt_step_yaml(monkeypatch):
    inputs = ['']
    input_generator = (i for i in inputs)
    monkeypatch.setattr('__builtin__.raw_input', lambda prompt: next(input_generator))
    
    recipe = RecipeObject.FromFile(os.path.join(os.path.dirname(__file__),"test_prompt_recipe.yaml"))
    start_time = time.time()
    recipe.run()

    assert (time.time()-start_time) <  4.0
    assert (time.time()-start_time) >= 2.0

