import queue
import pytest
from iotile_transport_bled112.bled112_async import BLED112Adapter

@pytest.fixture(scope='function')
def bled112(loop, mock_hardware):
    ser, adapter = mock_hardware
    bled = BLED112Adapter(ser, loop=loop)

    loop.run_coroutine(bled.start())

    yield bled

    loop.run_coroutine(bled.stop())


def test_basic_init(bled112, mock_hardware):
    """Test that we initialize correctly and the bled112 comes up scanning."""

    _, adapter = mock_hardware

    assert adapter.scanning


def test_scanning(loop, bled112, mock_hardware):
    """Make sure we can scan for devices."""

    _, adapter = mock_hardware

    scanned_devices = queue.Queue()
    def _on_scan_callback(conn_string, _conn_id, name, event):
        nonlocal scanned_devices

        scanned_devices.put(event)

    bled112.register_monitor([None], ['device_seen'], _on_scan_callback)

    loop.run_coroutine(adapter.advertise)

    dev1 = scanned_devices.get(timeout=0.5)
    dev2 = scanned_devices.get(timeout=0.5)

    assert dev1 == 'a'
