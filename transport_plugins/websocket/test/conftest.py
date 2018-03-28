import pytest
import threading
import tornado.ioloop
from tornado import netutil
import socket
from iotilegateway.gateway import IOTileGateway
from iotile.core.hw.hwmanager import HardwareManager
from iotile_transport_websocket.virtual_websocket import WebSocketVirtualInterface
from iotile_transport_websocket.device_adapter import WebSocketDeviceAdapter


def get_unused_port():
    """Get an available port on localhost.

    Adapted from tornado source code.
    Returns:
        port (int): An unused port
    """

    sock = netutil.bind_sockets(None, '127.0.0.1', family=socket.AF_INET, reuse_port=False)[0]
    port = sock.getsockname()[1]
    return port


class WebSocketVirtualInterfaceTestFixture(threading.Thread):

    def __init__(self, interface_config, device):
        super(WebSocketVirtualInterfaceTestFixture, self).__init__()

        self.device = device

        self.interface = WebSocketVirtualInterface(interface_config)

        self.loop = tornado.ioloop.IOLoop.instance()
        self.loaded = threading.Event()

    def run(self):
        self.interface.start(self.device)

        tornado.ioloop.PeriodicCallback(self.interface.process, 1000, self.loop).start()

        self.loop.add_callback(self.loaded.set)

        self.loop.start()

        # Once loop is stopped
        self.interface.stop()

    def stop(self):
        """Stop the supervisor and synchronously wait for it to stop."""

        self.loop.add_callback(self.loop.stop)

        self.join(timeout=10.0)
        if self.is_alive():
            raise RuntimeError("Can't stop Virtual Interface thread...")


@pytest.fixture(scope="function")
def virtual_interface(request):
    port = get_unused_port()
    config = {
        'port': port
    }

    device = request.param

    virtual_interface_fixture = WebSocketVirtualInterfaceTestFixture(config, device)
    virtual_interface_fixture.start()

    signaled = virtual_interface_fixture.loaded.wait(2.0)
    if not signaled:
        raise ValueError("Could not start virtual interface service")

    yield port, virtual_interface_fixture.interface

    virtual_interface_fixture.stop()


@pytest.fixture(scope="function")
def hw(virtual_interface):
    port, _ = virtual_interface

    hw = HardwareManager(port="ws2:localhost:{}".format(port))

    yield hw

    hw.close()


@pytest.fixture(scope="function")
def gateway(request):
    port = get_unused_port()
    adapters_config = request.param
    config = {
        "agents": [
            {"name": "websockets2", "args": {"port": port}}
        ],
        "adapters": [adapters_config]
    }

    gateway = IOTileGateway(config)
    gateway.start()

    signaled = gateway.loaded.wait(2.0)
    if not signaled:
        raise ValueError("Could not start gateway")

    yield port, gateway.device_manager

    gateway.stop()


@pytest.fixture(scope="function")
def device_adapter(gateway, request):
    port, manager = gateway
    kwargs = request.param if hasattr(request, 'param') else {}

    adapter = WebSocketDeviceAdapter(port="localhost:{}".format(port), **kwargs)

    tornado.ioloop.PeriodicCallback(adapter.periodic_callback, 1000, manager._loop).start()

    yield adapter

    adapter.stop_sync()
