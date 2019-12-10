import uuid
import logging
import pytest
from iotile_transport_bled112.hardware.async_bled112 import AsyncBLED112


logger = logging.getLogger(__name__)

@pytest.fixture(scope='module')
def mock_bled112(loop, mock_hardware):
    ser, _ = mock_hardware

    bled = AsyncBLED112(ser, loop=loop)
    loop.run_coroutine(bled.start())

    yield bled

    loop.run_coroutine(bled.stop())


def test_basic_scan(mock_bled112, loop):
    loop.run_coroutine(mock_bled112.set_scan_parameters())


def test_system_scan(mock_bled112, loop):
    max_conns, active_conns = loop.run_coroutine(mock_bled112.query_systemstate())
    assert max_conns == 3
    assert active_conns == []


SERVICE = {
    uuid.UUID('0ff60f63-132c-e611-ba53-f73f00200000'): {'end_handle': 16,
                                                        'start_handle': 1,
                                                        'uuid_raw': uuid.UUID('0ff60f63-132c-e611-ba53-f73f00200000')}
}

def test_basic_connect(mock_bled112, loop):
    res = loop.run_coroutine(mock_bled112.connect('00:11:22:33:44:55'))
    assert res == 0

    try:
        res = loop.run_coroutine(mock_bled112.probe_services(0))
        assert res == SERVICE

        res = loop.run_coroutine(mock_bled112.probe_characteristics(0, res))
        assert len(res) == 1

        service = res[0]
        assert len(service.characteristics) == 6
    finally:
        loop.run_coroutine(mock_bled112.disconnect(0))
