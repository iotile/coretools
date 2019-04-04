import logging
import pytest
from iotilegateway.device import AggregatingDeviceAdapter
from iotile.core.hw.transport import VirtualDeviceAdapter
from iotile.core.hw.exceptions import DeviceAdapterError
from iotile.core.utilities import BackgroundEventLoop
from iotile.mock.devices import RealtimeTestDevice

def gen_realtime_device(iotile_id):
    return RealtimeTestDevice(dict(iotile_id=iotile_id))


@pytest.fixture(scope="function")
def loop():
    """A fresh background event loop."""

    loop = BackgroundEventLoop()

    loop.start()
    yield loop
    loop.stop()


@pytest.fixture(scope="function")
def adapter(loop):
    """An aggregating device adapter with 2 virtual adapters."""

    dev1 = gen_realtime_device(1)
    dev2 = gen_realtime_device(2)
    dev3 = gen_realtime_device(3)
    dev4 = gen_realtime_device(4)

    adapter1 = VirtualDeviceAdapter(devices=[dev1, dev2], loop=loop)
    adapter2 = VirtualDeviceAdapter(devices=[dev3, dev4], loop=loop)

    combined = AggregatingDeviceAdapter(adapters=[adapter1, adapter2], loop=loop)

    loop.run_coroutine(combined.start())
    yield combined, [adapter1, adapter2], [dev1, dev2, dev3, dev4]
    loop.run_coroutine(combined.stop())


def test_basic(loop, adapter):
    """Make sure combined adapter works at a basic level."""

    adapter, _sub, _devs = adapter

    loop.run_coroutine(adapter.probe())
    assert len(adapter.visible_devices()) == 4

    devs = set(adapter.visible_devices())
    assert devs == set(['device/1', 'device/2', 'device/3', 'device/4'])


def test_connect_disconnect(loop, adapter):
    """Make sure we can connect and disconnect from both adapters."""

    adapter, _sub, _devs = adapter

    loop.run_coroutine(adapter.probe())

    loop.run_coroutine(adapter.connect(1, 'device/1'))
    loop.run_coroutine(adapter.connect(2, 'device/2'))
    loop.run_coroutine(adapter.connect(3, 'device/3'))
    loop.run_coroutine(adapter.connect(4, 'device/4'))

    # Make sure connection attempts to connected devices fail.
    with pytest.raises(DeviceAdapterError):
        loop.run_coroutine(adapter.connect(1, 'device/1'))

    with pytest.raises(DeviceAdapterError):
        loop.run_coroutine(adapter.connect(1, 'adapter/0/1'))

    loop.run_coroutine(adapter.disconnect(1))

    # Test forcing a connection through a given adapter
    with pytest.raises(DeviceAdapterError):
        loop.run_coroutine(adapter.connect(1, 'adapter/1/1'))

    loop.run_coroutine(adapter.connect(1, 'adapter/0/1'))
