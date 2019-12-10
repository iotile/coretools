"""Configure marks to allow running actual hardware tests on computers with dongles."""

import pytest
from iotile_transport_bled112.hardware.emulator.mock_bled112 import MockBLED112
from iotile_transport_bled112.hardware.async_bled112 import AsyncBLED112
from iotile_transport_blelib.iotile import EmulatedBLEDevice
from iotile.core.hw.virtual.virtualdevice_simple import SimpleVirtualDevice
from iotile.core.utilities.async_tools import BackgroundEventLoop
import util.dummy_serial


def pytest_addoption(parser):
    parser.addoption("--hardware", action="store_true", dest="hardware",
                     help="run tests that need access to bled112 hardware (2 dongles required)")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "hardware(name): mark test to run only when hardware is available"
    )


def pytest_runtest_setup(item):
    for _ in item.iter_markers(name="hardware"):
        if item.config.getoption('hardware') is False:
            pytest.skip("integration test requires external hardware and --hardware argument")


@pytest.fixture(scope='module')
def loop():
    loop = BackgroundEventLoop()

    loop.start()
    yield loop
    loop.stop()


@pytest.fixture(scope='module')
def mock_hardware(loop):
    serial_dev = util.dummy_serial.Serial('test', 230400, timeout=1, rtscts=True, exclusive=True)

    adapter = MockBLED112(3, write_func=serial_dev.inject, loop=loop)
    serial_dev.RESPONDER = adapter.inject_command_threadsafe

    dev1 = SimpleVirtualDevice(100, 'TestCN')
    dev1_ble = EmulatedBLEDevice("00:11:22:33:44:55", dev1)
    adapter.add_device(dev1_ble)

    dev2 = SimpleVirtualDevice(101, 'TestCN')
    dev2_ble = EmulatedBLEDevice("00:11:22:33:44:66", dev2)
    adapter.add_device(dev2_ble)

    yield serial_dev, adapter

    serial_dev.close()
