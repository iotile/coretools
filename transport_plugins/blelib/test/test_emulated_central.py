"""Tests of the behavior of the emulated central."""

import time
import pytest
from iotile.core.utilities.async_tools import BackgroundEventLoop
from iotile.mock.devices import ReportTestDevice
from iotile_transport_blelib.iotile.emulation import EmulatedBLECentral, EmulatedBLEDevice

@pytest.fixture(scope="module")
def loop():
    """A clean background event loop."""

    loop = BackgroundEventLoop()
    yield loop
    loop.stop()


@pytest.fixture(scope="function")
def two_dev_central(loop):
    """An emulated ble central with 2 emulated devices."""

    virtual_dev1 = ReportTestDevice(dict(iotile_id=1))
    virtual_dev2 = ReportTestDevice(dict(iotile_id=2, format="signed_list"))

    dev1 = EmulatedBLEDevice("00:00:00:00:00:00", virtual_dev1, loop=loop)
    dev2 = EmulatedBLEDevice("11:11:11:11:11:11", virtual_dev2, loop=loop)

    central = EmulatedBLECentral([dev1, dev2], dict(advertisement_rate=0.05), loop=loop)

    loop.run_coroutine(central.start())

    yield central, dev1, dev2

    loop.run_coroutine(central.stop())


def test_basic_scan(two_dev_central, loop):
    devs = []
    other = []

    def _queue_event(event):
        if event.event == 'advertisement':
            devs.append(event)
        else:
            other.append(event)

    central, _dev1, _dev2 = two_dev_central

    central.events.every_match(_queue_event)

    loop.run_coroutine(central.request_scan('abc'))

    # Make sure there's enough time for a periodic advertisement
    time.sleep(0.1)
    loop.run_coroutine(central.release_scan('abc'))

    loop.run_coroutine(central.events.wait_idle(0.5))

    assert len(devs) > 2
    assert len(other) == 2

    assert other[0].event == 'scan_started'
    assert other[1].event == 'scan_stopped'
