import pytest
import logging
import tempfile
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.hw.transport.adapter.sync_wrapper import SynchronousLegacyWrapper
from iotile.core.hw.transport import VirtualDeviceAdapter
from iotile.core.utilities import BackgroundEventLoop
from iotile_transport_socket_lib.unix_socket.unixsocket_adapter import UnixSocketDeviceAdapter
from iotile_transport_socket_lib.unix_socket.unixsocket_server import UnixSocketDeviceServer

logger = logging.getLogger(__name__)

@pytest.fixture(scope="function")
def loop():
    """Get a fresh BackgroundEventLoop."""

    event_loop = BackgroundEventLoop()
    event_loop.start()

    yield event_loop

    event_loop.stop()


@pytest.fixture(scope="function")
def server(request, loop):
    devices = request.param
    tmpdir = tempfile.TemporaryDirectory()
    socketfile = tmpdir.name+"/s"

    if not isinstance(devices, tuple):
        devices = (devices,)

    logger.info("Parametrizing server with devices: %s", devices)

    adapter = VirtualDeviceAdapter(devices=devices, loop=loop)
    loop.run_coroutine(adapter.start())

    args = {
        'path': socketfile
    }
    dev_server = UnixSocketDeviceServer(adapter, args, loop=loop)
    loop.run_coroutine(dev_server.start())

    yield socketfile, adapter

    loop.run_coroutine(dev_server.stop())
    loop.run_coroutine(adapter.stop())


@pytest.fixture(scope="function")
def hw(server):
    path, _ = server

    logger.info("Creating HardwareManager at with socket path %s", path)
    hw = HardwareManager(port="unix:{}".format(path))

    yield hw

    hw.close()


@pytest.fixture(scope="function")
def device_adapter(server, loop):
    path, _ = server

    adapter = UnixSocketDeviceAdapter(port=path, loop=loop)
    wrapper = SynchronousLegacyWrapper(adapter, loop=loop)
    yield wrapper

    wrapper.stop_sync()


@pytest.fixture(scope="function")
def multiple_device_adapter(server, loop):
    path, _ = server

    adapter1 = UnixSocketDeviceAdapter(port=path, loop=loop)
    adapter2 = UnixSocketDeviceAdapter(port=path, loop=loop)

    wrapper1 = SynchronousLegacyWrapper(adapter1, loop=loop)
    wrapper2 = SynchronousLegacyWrapper(adapter2, loop=loop)

    yield wrapper1, wrapper2

    wrapper1.stop_sync()
    wrapper2.stop_sync()
