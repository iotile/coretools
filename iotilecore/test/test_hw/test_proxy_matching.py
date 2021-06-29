from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.hw.proxy.proxy import TileBusProxyObject
from iotile.core.dev.semver import SemanticVersionRange
from typedargs import context
from iotile.core.dev import ComponentRegistry
import pytest
import os

# ProxyMatchTest1 - None
# ProxyMatchTest2 - None
# ProxyMatchTest3 - =1.0.0
# ProxyMatchTest4 - ^1.0.0
# ProxyMatchTest5 - ^1.1.5

@pytest.fixture
def proxy_variants_1():
    conf_file = os.path.join(os.path.dirname(__file__), 'proxy_match_tile_config.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    reg = ComponentRegistry()
    # None, ^1.0.0, ^1.1.5
    reg.register_extension('iotile.proxy', 'proxy_match_tile', ProxyMatchTest1)
    reg.register_extension('iotile.proxy', 'proxy_match_tile', ProxyMatchTest4)
    reg.register_extension('iotile.proxy', 'proxy_match_tile', ProxyMatchTest5)

    hw = HardwareManager('virtual:tile_based@%s' % conf_file)
    yield hw

    reg.clear_extensions()
    hw.close()

@pytest.fixture
def proxy_variants_2():
    conf_file = os.path.join(os.path.dirname(__file__), 'proxy_match_tile_config.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    reg = ComponentRegistry()
    # None, =1.0.0, ^1.0.0
    reg.register_extension('iotile.proxy', 'proxy_match_tile', ProxyMatchTest1)
    reg.register_extension('iotile.proxy', 'proxy_match_tile', ProxyMatchTest3)
    reg.register_extension('iotile.proxy', 'proxy_match_tile', ProxyMatchTest4)

    hw = HardwareManager('virtual:tile_based@%s' % conf_file)
    yield hw

    reg.clear_extensions()
    hw.close()

@pytest.fixture
def proxy_variants_3():
    conf_file = os.path.join(os.path.dirname(__file__), 'proxy_match_tile_config.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    reg = ComponentRegistry()
    # None, ^1.0.0
    reg.register_extension('iotile.proxy', 'proxy_match_tile', ProxyMatchTest1)
    reg.register_extension('iotile.proxy', 'proxy_match_tile', ProxyMatchTest4)

    hw = HardwareManager('virtual:tile_based@%s' % conf_file)
    yield hw

    reg.clear_extensions()
    hw.close()

@pytest.fixture
def proxy_variants_4():
    conf_file = os.path.join(os.path.dirname(__file__), 'proxy_match_tile_config.json')

    if '@' in conf_file or ',' in conf_file or ';' in conf_file:
        pytest.skip('Cannot pass device config because path has [@,;] in it')

    reg = ComponentRegistry()
    # None, None
    reg.register_extension('iotile.proxy', 'proxy_match_tile', ProxyMatchTest1)
    reg.register_extension('iotile.proxy', 'proxy_match_tile', ProxyMatchTest2)

    hw = HardwareManager('virtual:tile_based@%s' % conf_file)
    yield hw

    reg.clear_extensions()
    hw.close()

def test_variants_1(proxy_variants_1):
    hw = proxy_variants_1

    # ProxyMatchTest1 - None
    # ProxyMatchTest4 - ^1.0.0
    # ProxyMatchTest5 - ^1.1.5
    proxy = hw.get_proxy('pmtest', (1, 1, 5))
    assert issubclass(proxy, ProxyMatchTest5)

    proxy = hw.get_proxy('pmtest', (1, 1, 0))
    assert issubclass(proxy, ProxyMatchTest4)

    proxy = hw.get_proxy('pmtest', (0, 9, 0))
    assert issubclass(proxy, ProxyMatchTest1)

    proxy = hw.get_proxy('pmtest', (2, 1, 1))
    assert issubclass(proxy, ProxyMatchTest1)

def test_variants_2(proxy_variants_2):
    hw = proxy_variants_2

    # ProxyMatchTest1 - None
    # ProxyMatchTest3 - =1.0.0
    # ProxyMatchTest4 - ^1.0.0
    proxy = hw.get_proxy('pmtest', (1, 0, 0))
    assert issubclass(proxy, ProxyMatchTest3)

    proxy = hw.get_proxy('pmtest', (1, 0, 1))
    assert issubclass(proxy, ProxyMatchTest4)

    proxy = hw.get_proxy('pmtest', (0, 9, 0))
    assert issubclass(proxy, ProxyMatchTest1)

def test_variants_3(proxy_variants_3):
    hw = proxy_variants_3

    # ProxyMatchTest1 - None
    # ProxyMatchTest4 - ^1.0.0
    proxy = hw.get_proxy('pmtest', (1, 1, 0))
    assert issubclass(proxy, ProxyMatchTest4)

    proxy = hw.get_proxy('pmtest', (2, 0, 1))
    assert issubclass(proxy, ProxyMatchTest1)

    proxy = hw.get_proxy('pmtest', (0, 9, 0))
    assert issubclass(proxy, ProxyMatchTest1)

def test_variants_4(proxy_variants_4):
    hw = proxy_variants_4

    # ProxyMatchTest1 - None
    # ProxyMatchTest2 - None
    proxy = hw.get_proxy('pmtest', (1, 0, 0))
    assert issubclass(proxy, ProxyMatchTest2)

    proxy = hw.get_proxy('pmtest', (1, 0, 1))
    assert issubclass(proxy, ProxyMatchTest2)

    proxy = hw.get_proxy('pmtest', (0, 9, 0))
    assert issubclass(proxy, ProxyMatchTest2)

@context("ProxyMatchTest1")
class ProxyMatchTest1(TileBusProxyObject):
    @classmethod
    def ModuleName(cls):
        return 'pmtest'

@context("ProxyMatchTest2")
class ProxyMatchTest2(TileBusProxyObject):
    @classmethod
    def ModuleName(cls):
        return 'pmtest'

@context("ProxyMatchTest3")
class ProxyMatchTest3(TileBusProxyObject):
    @classmethod
    def ModuleName(cls):
        return 'pmtest'

    @classmethod
    def ModuleVersion(cls):
        return SemanticVersionRange.FromString('=1.0.0')

@context("ProxyMatchTest4")
class ProxyMatchTest4(TileBusProxyObject):
    @classmethod
    def ModuleName(cls):
        return 'pmtest'

    @classmethod
    def ModuleVersion(cls):
        return SemanticVersionRange.FromString('^1.0.0')

@context("ProxyMatchTest5")
class ProxyMatchTest5(TileBusProxyObject):
    @classmethod
    def ModuleName(cls):
        return 'pmtest'

    @classmethod
    def ModuleVersion(cls):
        return SemanticVersionRange.FromString('^1.1.5')
