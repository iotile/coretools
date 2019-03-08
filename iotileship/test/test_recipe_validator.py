"""Make sure that invalid recipe files are rejected """

import os
import pytest
from iotile.ship import RecipeObject, RecipeFileInvalid, UnknownRecipeResourceType


def load_recipe(filename):
    """Load a recipe from the recipes folder."""

    folder = os.path.dirname(__file__)
    return RecipeObject.FromFile(os.path.join(folder, 'recipes', filename), {'SyncCloudStep': object()}, {'hardware_manager': object()})


def test_valid_recipe():
    """Make sure we can load a valid recipe."""

    load_recipe('valid_recipe.yaml')


def test_invalid_step():
    """Make sure we detect an invalid step."""

    with pytest.raises(RecipeFileInvalid):
        load_recipe('invalid_step.yaml')


def test_shared_resource():
    """Make sure we allow parsing a shared resource."""

    load_recipe('shared_resources.yaml')


def test_using_invalid_resource():
    """Make sure we detect using an undeclared resource in use, open_before, close_after."""

    with pytest.raises(RecipeFileInvalid):
        load_recipe('undeclared_use.yaml')

    with pytest.raises(RecipeFileInvalid):
        load_recipe('undeclared_open.yaml')

    with pytest.raises(RecipeFileInvalid):
        load_recipe('undeclared_close.yaml')


def test_unknown_resource():
    """Make sure we throw an exception on unknown resource types."""

    with pytest.raises(UnknownRecipeResourceType):
        load_recipe('unknown_resource.yaml')


def test_variable_finding():
    """Make sure we can find variables reliably."""

    recipe = load_recipe('variable_finding.yaml')

    assert len(recipe.defaults) == 1
    assert recipe.free_variables == set(['test_1', 'test_2', 'test_3', 'test_4', 'test_5', 'Test_6'])
    assert recipe.required_variables == (recipe.free_variables - set(['test_1']))
    assert recipe.optional_variables == set(['test_1'])


def test_resource_renaming():
    """Make sure we can use resource as name statements."""

    recipe = load_recipe('shared_resources.yaml')

    step = recipe.steps[0]
    assert step.resources.used['internal_hardware'] == 'hardware'
