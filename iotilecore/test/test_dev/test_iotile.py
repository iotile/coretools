from __future__ import print_function
import pytest
import datetime
from dateutil.tz import tzutc
import os
from iotile.core.dev.iotileobj import IOTile, SemanticVersion
from iotile.core.exceptions import DataError


def load_tile(name):
    parent = os.path.dirname(__file__)
    path = os.path.join(parent, name)

    return IOTile(path)


def relative_paths(paths):
    """Get relative paths to this test file."""

    basedir = os.path.dirname(__file__)
    return [os.path.relpath(x, start=basedir) for x in paths]


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


def test_builtoldstyle_component():
    """Make sure we can load a v2 file format component."""
    tile = load_tile('oldstyle_built_component')

    assert tile.release is False
    assert tile.short_name == 'tile_gpio'
    assert tile.output_folder != tile.folder
    assert tile.can_release is False
    assert tile.release_date == datetime.datetime(2018, 12, 5, 21, 50, 38, 283000)


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


def test_basic_product_finding():
    """Make sure find_products works."""


    tile_dev = load_tile('comp_w_products')
    tile_rel = load_tile('releasemode_comp_w_prod')

    assert tile_dev.release is False
    assert tile_rel.release is True

    assert tile_dev.find_products('random_type') == []
    assert tile_rel.find_products('random_type') == []

    # Make sure unicode works
    assert tile_dev.find_products('include_directories') == tile_dev.find_products(u'include_directories')


def test_include_product_finding():
    """Make sure finding include_directories works."""

    tile_dev = load_tile('comp_w_products')
    tile_rel = load_tile('releasemode_comp_w_prod')

    assert tile_dev.release is False
    assert tile_rel.release is True

    assert tile_dev.find_products('random_type') == []
    assert tile_rel.find_products('random_type') == []

    # Test include_path finding
    inc_dev = tile_dev.find_products('include_directories')
    inc_rel = tile_rel.find_products('include_directories')

    assert len(inc_dev) == 12
    assert len(inc_rel) == 12

    rel_inc_dev = relative_paths(inc_dev)
    rel_inc_rel = relative_paths(inc_rel)

    for rel_dev, rel_rel in zip(rel_inc_dev, rel_inc_rel):
        assert rel_dev.startswith(os.path.join("comp_w_products", "build", "output", "include"))
        assert rel_rel.startswith(os.path.join("releasemode_comp_w_prod", "include"))


def test_library_finding():
    """Make sure finding libraries works."""

    tile_dev = load_tile('comp_w_products')

    lib_dev = tile_dev.find_products('library')
    assert lib_dev == ['libcontroller_nrf52832.a']


def test_type_package_finding():
    """Make sure we can find type packages."""

    tile_dev = load_tile('comp_w_products')
    tile_rel = load_tile('releasemode_comp_w_prod')

    dev_types = tile_dev.find_products('type_package')
    rel_types = tile_rel.find_products('type_package')

    assert len(dev_types) == 1
    assert len(rel_types) == 1

    assert relative_paths(dev_types) == [os.path.join('comp_w_products', 'python', 'lib_controller_types')]
    assert relative_paths(rel_types) == [os.path.join('releasemode_comp_w_prod', 'python', 'lib_controller_types')]


def test_tilebus_definition_finding():
    """Make sure we can find tilebus definitions."""

    tile_dev = load_tile('comp_w_products')
    tile_rel = load_tile('releasemode_comp_w_prod')

    dev_bus = tile_dev.find_products('tilebus_definitions')
    rel_bus = tile_rel.find_products('tilebus_definitions')

    assert len(dev_bus) == 8
    assert len(rel_bus) == 8

    rel_dev = relative_paths(dev_bus)
    rel_rel = relative_paths(rel_bus)

    # Test one list definition and one string definition
    assert rel_dev[0] == os.path.join('comp_w_products', 'firmware', 'src', 'test_interface', 'test_interface.bus')
    assert rel_rel[0] == os.path.join('releasemode_comp_w_prod', 'tilebus', 'test_interface.bus')

    assert rel_dev[-1] == os.path.join('comp_w_products', 'firmware', 'src', 'version', 'version.bus')
    assert rel_rel[-1] == os.path.join('releasemode_comp_w_prod', 'tilebus', 'version.bus')


def test_firmware_image_finding():
    """Make sure we can find firmware images."""

    tile_dev = load_tile('comp_w_products')
    tile_rel = load_tile('releasemode_comp_w_prod')

    dev_fw = tile_dev.find_products('firmware_image')
    rel_fw = tile_rel.find_products('firmware_image')

    assert len(dev_fw) == 1
    assert len(rel_fw) == 1

    assert relative_paths(dev_fw) == [os.path.join("comp_w_products", "build", "output", "controller_nrf52832.elf")]
    assert relative_paths(rel_fw) == [os.path.join("releasemode_comp_w_prod", "controller_nrf52832.elf")]


def test_linker_script_finding():
    """Make sure we can find linker scripts."""

    tile_dev = load_tile('comp_w_products')
    tile_rel = load_tile('releasemode_comp_w_prod')

    dev_ld = tile_dev.find_products('linker_script')
    rel_ld = tile_rel.find_products('linker_script')

    assert len(dev_ld) == 1
    assert len(rel_ld) == 1

    assert relative_paths(dev_ld) == [os.path.join("comp_w_products", "build", "output", "linker", "link.ld")]
    assert relative_paths(rel_ld) == [os.path.join("releasemode_comp_w_prod", "linker", "link.ld")]


def test_proxy_module_finding():
    """Make sure we can find proxy_modules."""

    tile_dev = load_tile('comp_w_products')
    tile_rel = load_tile('releasemode_comp_w_prod')

    dev_types = tile_dev.find_products('proxy_module')
    rel_types = tile_rel.find_products('proxy_module')

    assert len(dev_types) == 1
    assert len(rel_types) == 1

    assert relative_paths(dev_types) == [os.path.join('comp_w_products', 'python', 'proxy.py')]
    assert relative_paths(rel_types) == [os.path.join('releasemode_comp_w_prod', 'python', 'proxy.py')]


def test_build_step_finding():
    """Make sure we can find build steps."""

    tile_dev = load_tile('comp_w_products')
    tile_rel = load_tile('releasemode_comp_w_prod')

    dev_types = tile_dev.find_products('build_step')
    rel_types = tile_rel.find_products('build_step')

    assert len(dev_types) == 1
    assert len(rel_types) == 1

    assert relative_paths(dev_types) == [os.path.join('comp_w_products', 'python', 'buildstep.py:MyStep')]
    assert relative_paths(rel_types) == [os.path.join('releasemode_comp_w_prod', 'python', 'buildstep.py:MyStep')]


def test_unicode_finding():
    """Make sure unicode strings work in find_products()."""

    tile_dev = load_tile('comp_w_products')
    assert tile_dev.find_products('app_module') == tile_dev.find_products(u'app_module')


def test_app_module_finding():
    """Make sure we can find app modules."""

    tile_dev = load_tile('comp_w_products')
    tile_rel = load_tile('releasemode_comp_w_prod')

    dev_types = tile_dev.find_products('app_module')
    rel_types = tile_rel.find_products('app_module')

    assert len(dev_types) == 1
    assert len(rel_types) == 1

    assert relative_paths(dev_types) == [os.path.join('comp_w_products', 'python', 'app.py')]
    assert relative_paths(rel_types) == [os.path.join('releasemode_comp_w_prod', 'python', 'app.py')]


def test_proxy_plugin_finding():
    """Make sure we can find proxy_plugins."""

    tile_dev = load_tile('comp_w_products')
    tile_rel = load_tile('releasemode_comp_w_prod')

    dev_bus = tile_dev.find_products('proxy_plugin')
    rel_bus = tile_rel.find_products('proxy_plugin')

    assert len(dev_bus) == 5
    assert len(rel_bus) == 5

    rel_dev = sorted(relative_paths(dev_bus))
    rel_rel = sorted(relative_paths(rel_bus))

    assert rel_dev[0] == os.path.join('comp_w_products', 'python', 'configmanager.py')
    assert rel_rel[0] == os.path.join('releasemode_comp_w_prod', 'python', 'configmanager.py')


def test_product_filtering():
    """Make sure we can filter products."""

    tile_dev = load_tile('comp_w_products')
    assert len(tile_dev.find_products('proxy_plugin')) == 5

    tile_dev.filter_products(['include_directories'])
    assert len(tile_dev.find_products('proxy_plugin')) == 0
