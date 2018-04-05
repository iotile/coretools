import os
import time
import pytest
from iotile.core.hw import HardwareManager
from iotile.ship.recipe_manager import RecipeManager


class MockHardwareManResource(object):
    def __init__(self, hardware, iotile_id):
        self.hwman = hardware
        self.iotile_id = iotile_id

    def open(self):
        self.hwman.connect(self.iotile_id)

    def close(self):
        self.hwman.disconnect()


@pytest.fixture
def resman():
    """Create a recipe manager."""

    man = RecipeManager()
    man.add_recipe_folder(os.path.join(os.path.dirname(__file__), 'test_recipes'))  # includes recipe.yaml
    return man


@pytest.fixture
def recipe_fixture(request, resman):
    """Create a fixture with a hardware manager connected to our reference dev."""

    recipe = resman.get_recipe(request.param)

    hw = HardwareManager(port="virtual:reference_1_0")

    try:
        recipe.run(None, {'hardware': MockHardwareManResource(hw, 1)})

        yield recipe, hw, hw.stream.adapter.devices[1]
    finally:
        hw.close()

@pytest.mark.parametrize("recipe_fixture", [('test_ota')], indirect=True)
def test_ota_script(recipe_fixture):
    """Test that sending an OTA script actually works."""

    recipe, hw, device = recipe_fixture

    assert device.controller.script_error is None
    assert len(device.controller.parsed_script.records) == 2
