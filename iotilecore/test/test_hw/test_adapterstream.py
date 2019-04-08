"""Tests of the AdapterStream class.

The AdapterStream converts an AbstractDeviceAdapter into a nice, synchronous,
non-coroutine based interface for use from HardwareManager or a simple script.
"""

import pytest
from iotile.core.hw.transport import AdapterStream
from iotile.core.utilities import BackgroundEventLoop


@pytest.fixture(scope="function")
def loop():
    """A clean event loop."""

    loop = BackgroundEventLoop()
    loop.start()
    yield loop
    loop.stop()


@pytest.fixture(scope="function")
def stream():
    """A fresh adapter stream."""

    pass
