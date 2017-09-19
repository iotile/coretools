import pytest
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.exceptions import HardwareError
import time

def pytest_addoption(parser):
    parser.addoption('--port', default="bled112", help="Port to use to connect to iotile device")
    parser.addoption('--uuid', action="append", default=[], help="Device UUIDs to run tests on")
    parser.addoption('--tile', action="append", default=[], help="Device tile addresses to run tests on")

def pytest_generate_tests(metafunc):
    if 'port' in metafunc.fixturenames:
        port = metafunc.config.option.port

        metafunc.parametrize("port", [port], scope='session')

    if 'device_id' in metafunc.fixturenames:
        ids = [int(x, 0) for x in metafunc.config.option.uuid]
        metafunc.parametrize("device_id", ids, scope='session')

    if 'tile' in metafunc.fixturenames:
        ids = [int(x, 0) for x in metafunc.config.option.tile]
        metafunc.parametrize("tile", ids, scope='session')

@pytest.fixture(scope='module')
def device(port, device_id):
    """Return a HardwareManager instance connected to an IOTile Device

    This fixture shares the same device among all tests in the same module
    """
    with HardwareManager(port=port) as hw:
        # Sometimes in congested wireless environments we can miss the
        # device advertisement, so attempt the connection several times
        # before giving up to improve test robustness.
        max_attempts = 3
        for _i in xrange(0, max_attempts):
            try:
                hw.connect(device_id)
                break
            except HardwareError:
                time.sleep(1)
        hw.enable_streaming()
        yield hw
        hw.disconnect()

@pytest.fixture(scope='function')
def per_test_device(port, device_id):
    """Return a HardwareManager instance connected to an IOTile Device

    This fixture creates and tears down the connection for each test
    """
    with HardwareManager(port=port) as hw:
        max_attempts = 3
        for _i in xrange(0, max_attempts):
            try:
                hw.connect(device_id)
                break
            except HardwareError:
                time.sleep(1)

        hw.enable_streaming()
        yield hw
        hw.disconnect()
