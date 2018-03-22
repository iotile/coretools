from iotile.core.dev.iotileobj import IOTile, SemanticVersion
from iotile.core.exceptions import DataError
import pytest
import datetime
from dateutil.tz import tzutc
import os


def load_tile(name):
    parent = os.path.dirname(__file__)
    path = os.path.join(parent, name)

    return IOTile(path)


def test_load_releasemode():
    tile = load_tile('releasemode_component')

    assert tile.release is True
    assert tile.short_name == 'tile_gpio'
    assert tile.output_folder == tile.folder


def test_load_devmode():
    tile = load_tile('devmode_component')

    assert tile.release is False
    assert tile.short_name == 'tile_gpio'
    assert tile.output_folder != tile.folder
    assert tile.can_release is False

    assert tile.targets == ['lpc824']


def test_load_oldstyle():
    tile = load_tile('oldstyle_component')

    assert tile.release is False
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


def test_load_invalidsteps():
    with pytest.raises(DataError):
        _tile = load_tile('releasesteps_invalid_component')


def test_newstyle_component():
    """Make sure we can load a v2 file format component."""
    tile = load_tile('newstyle_comp')

    assert tile.release is False
    assert tile.release_date is None
    assert tile.short_name == 'tile_gpio'
    assert tile.output_folder != tile.folder
    assert tile.can_release is False
    assert tile.targets == ['lpc824']


def test_releasednewstyle_component():
    """Make sure we can load a v2 file format component."""
    tile = load_tile('newstyle_released_comp')

    assert tile.release is True
    assert tile.release_date == datetime.datetime(2018, 3, 15, 14, 42, tzinfo=tzutc())
    assert tile.short_name == 'tile_gpio'
    assert tile.output_folder == tile.folder
    assert tile.can_release is False
    assert tile.targets == []


def test_builtnewstyle_component():
    """Make sure we can load a v2 file format component."""
    tile = load_tile('newstyle_built_comp')

    assert tile.release is False
    assert tile.short_name == 'tile_gpio'
    assert tile.output_folder != tile.folder
    assert tile.can_release is False
    assert tile.release_date == datetime.datetime(2018, 3, 15, 14, 42, tzinfo=tzutc())

def test_load_invaliddepends():
    with pytest.raises(DataError) as excinfo:
        _tile = load_tile('comp_w_depslist')

    assert excinfo.value.msg == "module must have a depends key that is a dictionary"


def test_deprange_parsing():
    tile = load_tile('dep_version_comp')

    print(tile.dependencies[0]['required_version_string'])
    reqver = tile.dependencies[0]['required_version']
    print(reqver._disjuncts[0][0])

    assert reqver.check(SemanticVersion.FromString('1.0.0'))
    assert reqver.check(SemanticVersion.FromString('1.1.0'))
    assert not reqver.check(SemanticVersion.FromString('2.0.0'))


def test_depversion_tracking():
    """Make sure release mode components load as-built dependency versions
    """

    tile = load_tile("releasemode_comp_depver")

    assert len(tile.dependency_versions) == 3
    assert tile.dependency_versions['iotile_standard_library_common'] == SemanticVersion.FromString('1.0.0')
    assert tile.dependency_versions['iotile_standard_library_liblpc824'] == SemanticVersion.FromString('2.0.0')
    assert tile.dependency_versions['iotile_standard_library_libcortexm0p_runtime'] == SemanticVersion.FromString('3.0.0')


def test_depfinding_basic():
    """Make sure IOTile() finds dependencies listed with a module
    """

    tile = load_tile('comp_w_deps')

    assert len(tile.dependencies) == 3

    deps = set([x['name'] for x in tile.dependencies])
    assert 'dep1' in deps
    assert 'dep2' in deps
    assert 'dep3' in deps


def test_depfinding_archs():
    """Make sure IOTile also finds dependencies specified in architectures
    """

    tile = load_tile('comp_w_archdeps')

    assert len(tile.dependencies) == 4

    deps = set([x['name'] for x in tile.dependencies])

    assert 'dep1' in deps
    assert 'dep2' in deps
    assert 'dep3' in deps
    assert 'dep4' in deps


def test_depfinding_overlays():
    """Make sure IOTile also finds dependencies specified in architecture overlays
    """

    tile = load_tile('comp_w_overlaydeps')

    assert len(tile.dependencies) == 5

    deps = set([x['name'] for x in tile.dependencies])

    assert 'dep1' in deps
    assert 'dep2' in deps
    assert 'dep3' in deps
    assert 'dep4' in deps
    assert 'dep5' in deps
