import logging
import pytest
from iotile.core.utilities import BackgroundEventLoop
from iotile.core.hw.virtual import RPCDispatcher, tile_rpc
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.hw.proxy.proxy import TileBusProxyObject
from iotilegateway.supervisor import IOTileSupervisor, AsyncSupervisorClient, SupervisorClient

logger = logging.getLogger(__name__)


class BasicRPCDispatcher(RPCDispatcher):
    @tile_rpc(0x8000, "LL", "L")
    def add(self, arg1, arg2):
        logger.info("add called with %d and %d", arg1, arg2)
        return [arg1 + arg2]

    @tile_rpc(0x8001, "", "")
    def throw_exception(self):
        raise ValueError("Random error")

    @tile_rpc(0x8002, "", "L")
    def invalid_return(self):
        return [1, 2]


class BasicRPCDispatcherProxy(TileBusProxyObject):
    """A very basic proxy object for interacting with out BasicRPCDispatcher."""

    @classmethod
    def ModuleName(cls):
        return 'bsctst'

    def add(self, arg1, arg2):
        """Invoke the add function on the BasicRPCDispatcher."""

        res, = self.rpc(0x80, 0x00, arg1, arg2, arg_format="LL", result_format="L")
        return res


@pytest.fixture(scope="function")
def loop():
    """A clean background event loop."""

    loop = BackgroundEventLoop()
    loop.start()

    yield loop

    loop.stop()


@pytest.fixture(scope="function")
def bare_supervisor(loop):
    """A running supervisor with two connected status clients."""

    info = {
        'expected_services':
        [
            {
                "short_name": "service1",
                "long_name": "Service 1"
            },

            {
                "short_name": "service2",
                "long_name": "Service 2"
            }
        ],
        'port': None      # Bind an unused port for testing, the value
                          # will appear on visor.port
    }

    visor = IOTileSupervisor(info, loop=loop)

    loop.run_coroutine(visor.start())

    port = visor.port

    yield port, visor

    loop.run_coroutine(visor.stop())


@pytest.fixture(scope="function")
def async_supervisor(loop, bare_supervisor):
    """An asynchronous supervisor client connected to a supervisor."""

    port, visor = bare_supervisor

    client1 = AsyncSupervisorClient('ws://127.0.0.1:%d/services' % port, loop=loop)
    loop.run_coroutine(client1.start())

    yield visor, client1

    loop.run_coroutine(client1.stop())


@pytest.fixture(scope="function")
def sync_supervisor(loop, bare_supervisor):
    """An synchronous supervisor client connected to a supervisor."""

    port, visor = bare_supervisor

    client1 = SupervisorClient('ws://127.0.0.1:%d/services' % port, loop=loop)

    yield visor, client1

    client1.stop()


@pytest.fixture(scope="function")
def rpc_supervisor(loop, bare_supervisor):
    """A supervisor with an rpc agent and two clients one sync, one async."""

    port, visor = bare_supervisor

    client1 = AsyncSupervisorClient('ws://127.0.0.1:%d/services' % port, loop=loop)
    loop.run_coroutine(client1.start())

    client2 = SupervisorClient('ws://127.0.0.1:%d/services' % port, loop=loop)

    rpc_client = SupervisorClient('ws://127.0.0.1:%d/services' % port,
                                  dispatcher=BasicRPCDispatcher(),
                                  agent='service1', loop=loop)

    yield visor, client1, client2

    rpc_client.stop()
    client2.stop()
    loop.run_coroutine(client1.stop())
