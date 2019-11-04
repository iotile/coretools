import pytest
import logging
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.hw.transport.adapter.sync_wrapper import SynchronousLegacyWrapper
from iotile.core.hw.transport import VirtualDeviceAdapter
from iotile.core.utilities import BackgroundEventLoop
from iotile_transport_socket_lib.tcp_socket.tcpsocket_adapter import TcpSocketDeviceAdapter
from iotile_transport_socket_lib.tcp_socket.tcpsocket_server import TcpSocketDeviceServer

logger = logging.getLogger(__name__)

@pytest.fixture(scope="function")
def loop():
    """Get a fresh BackgroundEventLoop."""

    event_loop = BackgroundEventLoop()
    event_loop.start()

    yield event_loop

    event_loop.stop()


@pytest.fixture(scope="function")
def server( request, loop):
    devices = request.param

    if not isinstance(devices, tuple):
        devices = (devices,)

    logger.info("Parametrizing server with devices: %s", devices)

    adapter = VirtualDeviceAdapter(devices=devices, loop=loop)
    loop.run_coroutine(adapter.start())

    args = {
        'host': '127.0.0.1',
        'port': 0
    }

    dev_server = TcpSocketDeviceServer(adapter, args, loop=loop)
    loop.run_coroutine(dev_server.start())

    yield dev_server.implementation.port, adapter

    loop.run_coroutine(dev_server.stop())
    loop.run_coroutine(adapter.stop())


@pytest.fixture(scope="function")
def hw(server):
    port, _ = server

    logger.info("Creating HardwareManager at port %d", port)
    hw = HardwareManager(port="tcp:127.0.0.1:{}".format(port))

    yield hw

    hw.close()


@pytest.fixture(scope="function")
def device_adapter(server, loop):
    port, _ = server

    adapter = TcpSocketDeviceAdapter(port="127.0.0.1:{}".format(port), loop=loop)
    wrapper = SynchronousLegacyWrapper(adapter, loop=loop)
    yield wrapper

    wrapper.stop_sync()


@pytest.fixture(scope="function")
def multiple_device_adapter(server, loop):
    port, _ = server

    adapter1 = TcpSocketDeviceAdapter(port="127.0.0.1:{}".format(port), loop=loop)
    adapter2 = TcpSocketDeviceAdapter(port="127.0.0.1:{}".format(port), loop=loop)

    wrapper1 = SynchronousLegacyWrapper(adapter1, loop=loop)
    wrapper2 = SynchronousLegacyWrapper(adapter2, loop=loop)

    yield wrapper1, wrapper2

    wrapper1.stop_sync()
    wrapper2.stop_sync()
