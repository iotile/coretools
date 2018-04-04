import os
import time
import pytest

from iotile.ship.recipe import RecipeObject
from iotile.ship.recipe_manager import RecipeManager
from iotile.ship.exceptions import RecipeVariableNotPassed
from iotile.core.exceptions import ArgumentError


@pytest.fixture
def resman():
    man = RecipeManager()
    man.add_recipe_folder(os.path.join(os.path.dirname(__file__), 'test_recipes'))  # includes recipe.yaml
    return man


def test_basic_yaml(resman):
    recipe = resman.get_recipe('test_basic_yaml')

    assert recipe.name == 'test_basic_yaml'
    assert recipe.steps[0][0].__name__ == 'WaitStep'

    assert recipe.steps[0][1]['seconds'] == 0.2


    start_time = time.time()
    recipe.run()
    run_time = time.time()-start_time
    assert run_time <= 0.3
    assert run_time >= 0.1


def test_replace_yaml(resman):
    recipe = resman.get_recipe('test_replace_recipe')
    variables = {"custom_wait_time": 1}

    start_time = time.time()
    recipe.run(variables)
    run_time = time.time()-start_time

    assert run_time <= 1.1
    assert run_time >= 0.9


def test_replace_yaml_fail(resman):
    #Should fail if no variables are passed
    recipe = resman.get_recipe('test_replace_recipe')
    with pytest.raises(RecipeVariableNotPassed):
        recipe.run()


def test_snippet(resman):
    recipe = resman.get_recipe('test_snippet')

    successful_variables = {
        'test_commmand' : 'tile_name',
        'test_output' : 'Simple'
    }
    recipe.run(successful_variables)

    unexpected_variables = {
        'test_commmand' : 'tile_name',
        'test_output' : 'Complicated'
    }
    with pytest.raises(ArgumentError):
        recipe.run(unexpected_variables)

    error_variables = {
        'test_commmand' : '"',
        'test_output' : 'Simple'
    }
    with pytest.raises(ArgumentError):
        recipe.run(error_variables)


def test_snippet_no_expect(resman):
    recipe = resman.get_recipe('test_snippet_no_expect')
    recipe.run()


def test_check_cloud_output(resman):
    resman.get_recipe('test_check_cloud_outputs')


def test_verify_device_step(resman):
    resman.get_recipe('test_verify_device_step')


def test_hardware_manager_resource(resman):
    """Make sure we can create a shared hardware manager resource."""

    recipe = resman.get_recipe('test_hardware_manager_resource')
    recipe.run()
