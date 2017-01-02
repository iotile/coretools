from iotile.core.dev.iotileobj import IOTile
from iotile.core.exceptions import DataError
import pytest
import os

def load_tile(name):
    parent = os.path.dirname(__file__)
    path = os.path.join(parent, name)

    return IOTile(path)

def test_load_releasemode():
    tile = load_tile('releasemode_component')

    assert tile.release == True
    assert tile.short_name == 'tile_gpio'
    assert tile.output_folder == tile.folder

def test_load_devmode():
    tile = load_tile('devmode_component')

    assert tile.release == False
    assert tile.short_name == 'tile_gpio'
    assert tile.output_folder != tile.folder
    assert tile.can_release is False

def test_load_oldstyle():
    tile = load_tile('oldstyle_component')

    assert tile.release == False
    assert tile.short_name == 'tile_gpio'
    assert tile.output_folder != tile.folder

def test_load_releasesteps():
    tile = load_tile('releasesteps_good_component')

    assert tile.release is False
    assert tile.can_release is True
    assert len(tile.release_steps) == 2

    step1 = tile.release_steps[0]
    step2 = tile.release_steps[1]

    assert step1.provider == 'github'
    assert step1.args['repo'] == 'tile_gpio'
    assert step1.args['owner'] == 'iotile'

    assert step2.provider == 'gemfury'
    assert len(step2.args) == 0

def  test_load_invalidsteps():
    with pytest.raises(DataError):
        tile = load_tile('releasesteps_invalid_component')
