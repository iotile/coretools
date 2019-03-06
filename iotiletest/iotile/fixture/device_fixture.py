import time
import pytest

from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.exceptions import HardwareError


def pytest_addoption(parser):
    parser.addoption('--port', default="bled112", help="Port to use to connect to iotile device")
    parser.addoption('--uuid', action="append", default=[], help="Device UUIDs to run tests on")
    parser.addoption('--tile', action="append", default=[], help="Device tile addresses to run tests on")
    parser.addoption('--direct', action="store_true", help="Run script on device given by this connection string")
    parser.addoption('--record', help="Record all RPCs to a csv file")


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

    if 'direct' in metafunc.fixturenames:
        connections = [metafunc.config.option.direct]
        metafunc.parametrize("direct", connections, scope='session')

    if 'record' in metafunc.fixturenames:
        metafunc.parametrize("record", [metafunc.config.option.record], scope='session')


@pytest.fixture(scope='module')
def device(port, device_id, direct, record, request):
    """Return a HardwareManager instance connected to an IOTile Device

    This fixture shares the same device among all tests in the same module
    """

    if record is not None:
        record = _build_record_string(record, request, module=True)

    with HardwareManager(port=port, record=record) as hw:
        # Sometimes in congested wireless environments we can miss the
        # device advertisement, so attempt the connection several times
        # before giving up to improve test robustness.
        max_attempts = 3
        i = 0
        for i in range(0, max_attempts):
            try:
                if direct:
                    hw.connect_direct(direct)
                else:
                    hw.connect(device_id)
                break
            except HardwareError:
                time.sleep(1)

        if i == max_attempts:
            pytest.fail("Could not connect to device after %d attempts, failing" % max_attempts)
            return

        hw.enable_streaming()
        yield hw
        hw.disconnect()


@pytest.fixture(scope='function')
def per_test_device(port, device_id, direct, record, request):
    """Return a HardwareManager instance connected to an IOTile Device

    This fixture creates and tears down the connection for each test
    """

    if record is not None:
        record = _build_record_string(record, request, module=False)

    with HardwareManager(port=port, record=record) as hw:
        max_attempts = 3
        i = 0
        for i in range(0, max_attempts):
            try:
                if direct:
                    hw.connect_direct(direct)
                else:
                    hw.connect(device_id)
                break
            except HardwareError:
                time.sleep(1)

        if i == max_attempts:
            pytest.fail("Could not connect to device after %d attempts, failing" % max_attempts)
            return

        hw.enable_streaming()
        yield hw
        hw.disconnect()


def _build_record_string(name, request, module=True):
    """Build a proper string name to record connection information."""

    if '{}' not in name:
        return name

    if module:
        identifier = request.module.__name__
    else:
        identifier = request.node.originalname

    return name.format(identifier)
