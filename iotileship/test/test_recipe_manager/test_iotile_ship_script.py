import sys
import os.path
import pytest
import time
from iotile.ship.scripts.iotile_ship import main


class SystemExitError(Exception):
    """Internal error to signal that sys.exit was called."""
    pass

@pytest.fixture
def exitcode(monkeypatch):
    """Patch sys.exit so we can test argparse containing code."""

    def _fake_exit(code):
        raise SystemExitError(code)

    monkeypatch.setattr(sys, 'exit', _fake_exit)


def test_basic_help(exitcode):
    """Make sure the program can print help text."""

    with pytest.raises(SystemExitError):
        main(['--help'])


def test_basic_single(exitcode):
    """Make sure we can run a recipe for single devices."""

    recipe = os.path.join(os.path.dirname(__file__), 'test_recipes', 'test_basic_recipe.yaml')

    start_time  = time.time()
    retval      = main([recipe, '--uuid', '0x0'])
    total_time  = time.time()-start_time

    assert retval == 0

def test_basic_range(exitcode):
    """Make sure we can run a recipe for multiple devices."""

    recipe = os.path.join(os.path.dirname(__file__), 'test_recipes', 'test_basic_recipe.yaml')

    start_time  = time.time()
    retval      = main([recipe, '--uuid-range', '0x0-0x5'])
    total_time  = time.time()-start_time

    assert retval == 0


def test_basic_info(exitcode):
    """Make sure we can get the info of a recipe."""

    recipe = os.path.join(os.path.dirname(__file__), 'test_recipes', 'test_basic_recipe.yaml')

    start_time  = time.time()
    retval      = main([recipe, "--info"])
    total_time  = time.time()-start_time

    assert retval == 0

def test_config(exitcode):
    """Make sure we can get the info of a recipe."""

    recipe      = os.path.join(os.path.dirname(__file__), 'test_recipes', 'test_snippet.yaml')
    config_file = os.path.join(os.path.dirname(__file__), 'data', 'config.yaml')

    start_time  = time.time()
    retval      = main([recipe, "--config", config_file])
    total_time  = time.time()-start_time

    assert retval == 0
