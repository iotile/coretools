import uuid
import logging
import pytest
import serial
from iotile_transport_bled112.hardware.emulator.mock_bled112 import MockBLED112
from iotile_transport_bled112.hardware.async_bled112 import AsyncBLED112
from iotile.mock.mock_ble import MockBLEDevice
from iotile.core.hw.virtual.virtualdevice_simple import SimpleVirtualDevice
from iotile.core.utilities.async_tools import BackgroundEventLoop
import util.dummy_serial


logger = logging.getLogger(__name__)
@pytest.fixture(scope='module')
def loop():
    loop = BackgroundEventLoop()

    loop.start()
    yield loop
    loop.stop()


@pytest.fixture(scope='module')
def mock_bled112(loop):
    old_serial = serial.Serial
    serial.Serial = util.dummy_serial.Serial

    adapter = MockBLED112(3)

    dev1 = SimpleVirtualDevice(100, 'TestCN')
    dev1_ble = MockBLEDevice("00:11:22:33:44:55", dev1)
    adapter.add_device(dev1_ble)

    util.dummy_serial.RESPONSE_GENERATOR = adapter.generate_response

    serial_dev = serial.Serial('test', 230400, timeout=1, rtscts=True, exclusive=True)
    bled = AsyncBLED112(serial_dev, loop=loop)
    yield bled

    loop.run_coroutine(bled.stop())
    serial_dev.close()

    serial.Serial = old_serial


def test_basic_scan(mock_bled112, loop):
    loop.run_coroutine(mock_bled112.set_scan_parameters())


def test_system_scan(mock_bled112, loop):
    res = loop.run_coroutine(mock_bled112.query_systemstate())
    assert res['max_connections'] == 3
    assert len(res['active_connections']) == 0


SERVICE = {
    uuid.UUID('0ff60f63-132c-e611-ba53-f73f00200000'): {'end_handle': 15,
                                                        'start_handle': 1,
                                                        'uuid_raw': uuid.UUID('0ff60f63-132c-e611-ba53-f73f00200000')}
}

def test_basic_connect(mock_bled112, loop):
    res = loop.run_coroutine(mock_bled112.connect('00:11:22:33:44:55'))
    assert res == 0

    try:
        res = loop.run_coroutine(mock_bled112.probe_services(0))
        assert res == dict(services=SERVICE)

        res = loop.run_coroutine(mock_bled112.probe_characteristics(0, res['services']))
        assert len(res['services'][uuid.UUID('0ff60f63-132c-e611-ba53-f73f00200000')]['characteristics']) == 6
    finally:
        loop.run_coroutine(mock_bled112.disconnect(0))
