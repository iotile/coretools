import pytest
import os
import shutil
from iotile.core.exceptions import ExternalError
from iotile.build.dev.resolverchain import DependencyResolverChain
from iotile.mock.mock_resolver import MockDependencyResolver
from iotile.core.dev.iotileobj import IOTile
from iotile.core.dev.registry import ComponentRegistry
import re

def copytree(src, dst, symlinks=False, ignore=None):
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)

def copy_comp(source, tempdir):
    copytree(os.path.join(os.path.dirname(__file__), source), tempdir)
    return IOTile(tempdir)

def comp_path(name):
    return os.path.join(os.path.dirname(__file__), name)

@pytest.fixture
def chain_comp1_v11(request):
    chain = DependencyResolverChain()
    chain.rules = [(0, (re.compile('.*'), MockDependencyResolver, [comp_path('comp1_v1.1')]))]
    return chain

@pytest.fixture
def chain_comp1_v12(request):
    chain = DependencyResolverChain()
    chain.rules = [(0, (re.compile('.*'), MockDependencyResolver, [comp_path('comp1_v1.2')]))]
    return chain

@pytest.fixture
def chain_comp1_v20(request):
    chain = DependencyResolverChain()
    chain.rules = [(0, (re.compile('.*'), MockDependencyResolver, [comp_path('comp1_v2.0')]))]
    return chain

@pytest.fixture
def chain_composite(request):
    """Create a multirule chain that has the registry followed by the mock resolver
    """

    reg = ComponentRegistry()
    reg.add_component(comp_path('comp3_v1.0'))

    chain = DependencyResolverChain()
    chain.rules.append([10, (re.compile('.*'), MockDependencyResolver, [comp_path('comp1_v1.1')])])
    yield chain

    reg.remove_component('comp3')

def test_update_dependencies_basic(chain_comp1_v11, chain_comp1_v12, chain_comp1_v20, tmpdir):
    """Test to make sure we can find and install and update a dependency
    """

    tile = copy_comp('comp2_dev_v1.1', tmpdir.strpath)

    for dep in tile.dependencies:
        result = chain_comp1_v11.update_dependency(tile, dep)
        assert result == 'installed'

    for dep in tile.dependencies:
        result = chain_comp1_v11.update_dependency(tile, dep)
        assert result == 'already installed'

    for dep in tile.dependencies:
        result = chain_comp1_v12.update_dependency(tile, dep)
        assert result == 'updated'

    #version 2.0.0 doesn't meet our spec for deps
    for dep in tile.dependencies:
        result = chain_comp1_v20.update_dependency(tile, dep)
        assert result == 'already installed'

def test_registry_resolver(tmpdir):
    """Test to make sure that the registry resolver can install and update a dependency
    """

    reg = ComponentRegistry()
    chain = DependencyResolverChain()

    tile = copy_comp('comp2_dev_v1.1', tmpdir.strpath)

    try:
        reg.add_component(comp_path('comp1_v1.1'))
        for dep in tile.dependencies:
            result = chain.update_dependency(tile, dep)
            assert result == 'installed'

        for dep in tile.dependencies:
            result = chain.update_dependency(tile, dep)
            assert result == 'already installed'

        reg.remove_component('comp1')
        reg.add_component(comp_path('comp1_v1.2'))

        for dep in tile.dependencies:
            result = chain.update_dependency(tile, dep)
            assert result == 'updated'

        reg.remove_component('comp1')
        reg.add_component(comp_path('comp1_v2.0'))

        for dep in tile.dependencies:
            result = chain.update_dependency(tile, dep)
            assert result == 'already installed'
    finally:
        reg.remove_component('comp1')

def test_registry_resolver_unbuilt(tmpdir):
    """Make sure we throw an error if we are asked to install an unbuilt component
    """

    reg = ComponentRegistry()
    chain = DependencyResolverChain()

    tile = copy_comp('comp2_dev_v1.1', tmpdir.strpath)

    try:
        reg.add_component(comp_path('comp1_v1.1_unbuilt'))
        with pytest.raises(ExternalError) as excinfo:
            for dep in tile.dependencies:
                result = chain.update_dependency(tile, dep)

        assert excinfo.value.msg == 'Component found in registry but has not been built'
    finally:
        reg.remove_component('comp1')

def test_registry_resolver_built_invalid(tmpdir):
    """Make sure we throw an error if we are asked to install an invalid built component
    """

    reg = ComponentRegistry()
    chain = DependencyResolverChain()

    tile = copy_comp('comp2_dev_v1.1', tmpdir.strpath)

    try:
        reg.add_component(comp_path('comp1_v1.1_built_empty'))
        with pytest.raises(ExternalError) as excinfo:
            for dep in tile.dependencies:
                result = chain.update_dependency(tile, dep)

        assert excinfo.value.msg == 'Component found in registry but its build/output folder is not valid'
    finally:
        reg.remove_component('comp1')

def test_multiple_resolvers(tmpdir, chain_composite):
    """Test to make sure that finding deps via multiple resolvers works
    """

    tile = copy_comp('comp4_v1.0', tmpdir.strpath)

    for dep in tile.dependencies:
        result = chain_composite.update_dependency(tile, dep)
        assert result == 'installed'

    #If nothing changes, no changes should be made
    for dep in tile.dependencies:
        result = chain_composite.update_dependency(tile, dep)
        assert result == 'already installed'

    #Now simulate a new release in the mock resolver
    chain_composite.rules[-1][1] = (re.compile('.*'), MockDependencyResolver, [comp_path('comp1_v1.2')])
    
    for dep in tile.dependencies:
        result = chain_composite.update_dependency(tile, dep)
        if dep['unique_id'] == 'comp1':
            assert result == 'updated'
        else:
            assert result == 'already installed'

    #If nothing changes, no changes should be made
    for dep in tile.dependencies:
        result = chain_composite.update_dependency(tile, dep)
        assert result == 'already installed'
