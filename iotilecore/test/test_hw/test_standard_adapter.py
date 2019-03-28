"""Test the StandardDeviceAdapter class."""

import pytest
from iotile.core.utilities import BackgroundEventLoop
from iotile.core.hw.transport.adapter import StandardDeviceAdapter

@pytest.fixture(scope="function")
def adapter_loop():
    """A clean event loop and device adapter."""

    loop = BackgroundEventLoop()
    adapter = StandardDeviceAdapter(loop=loop)

    loop.start()

    yield adapter, loop

    loop.stop()


def test_register_monitors(adapter_loop):
    """Make sure we can register monitors."""

    adapter, loop = adapter_loop

    events = []
    async def _save_notification(*args):
        events.append(args)

    handle = adapter.register_monitor([None], ['device_seen'], _save_notification)

    pairs = list(adapter.iter_monitors())
    assert len(pairs) == 1
    assert pairs[0] == (None, 'device_seen', handle)

    loop.run_coroutine(adapter.notify_event('abc', 'device_seen', {}))

    assert len(events) == 1
