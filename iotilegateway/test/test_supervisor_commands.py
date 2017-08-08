import pytest
from iotile.core.hw.virtual import RPCDispatcher, tile_rpc
from iotilegateway.supervisor import IOTileSupervisor, ServiceStatusClient


class BasicRPCDispatcher(RPCDispatcher):
    @tile_rpc(0x8000, "LL", "L")
    def add(self, arg1, arg2):
        return [arg1 + arg2]


@pytest.fixture(scope="function")
def supervisor():
    """A running supervisor with two connected status clients."""

    info = {
        'expected_services':
        [
            {
                "short_name": "service_1",
                "long_name": "A test service"
            },

            {
                "short_name": "service_2",
                "long_name": "A second test service"
            }
        ],
        'port': 'unused'  # Bind an unused port for testing, the value will appear on visor.port after visor.loaded is set
    }

    visor = IOTileSupervisor(info)

    visor.start()
    signaled = visor.loaded.wait(2.0)
    if not signaled:
        raise ValueError("Could not start supervisor service")

    port = visor.port

    client1 = ServiceStatusClient('ws://127.0.0.1:%d/services' % port)
    client2 = ServiceStatusClient('ws://127.0.0.1:%d/services' % port)

    yield visor, client1, client2

    client1.stop()
    client2.stop()
    visor.stop()

@pytest.fixture(scope="function")
def rpc_agent(supervisor):
    """Register an RPC agent on one of the clients."""

    visor, _client1, client2 = supervisor

    port = visor.port
    client1 = ServiceStatusClient('ws://127.0.0.1:%d/services' % port, dispatcher=BasicRPCDispatcher(), agent='service_1')

    yield visor, client1, client2

    client1.stop()


def test_send_rpc_unknown(supervisor):
    """Make sure we can send an RPC at a basic level."""

    _visor, client1, _client2 = supervisor

    resp = client1.send_rpc('service_1', 0x8000, "")
    assert resp['result'] == 'service_not_found'


def test_register_agent(supervisor):
    """Make sure we can register as an agent."""

    visor, client1, _client2 = supervisor

    assert len(visor.service_manager.agents) == 0
    client1.register_agent('service_1')

    assert len(visor.service_manager.agents) == 1
    assert 'service_1' in visor.service_manager.agents


def test_send_rpc_timeout(supervisor):
    """Make sure we RPCs get forwarded and timeout when not answered."""

    _visor, client1, client2 = supervisor

    client1.register_agent('service_1')
    resp = client2.send_rpc('service_1', 0x8000, "", timeout=0.01)
    assert resp['result'] == 'timeout'


def test_send_rpc_success(rpc_agent):
    """Make sure we can send RPCs that are implemented."""

    _visor, client1, client2 = rpc_agent

    resp = client2.send_rpc('service_1', 0x8000, b'\x00'*8)
    assert resp['result'] == 'success'
    assert resp['response'] == b'\x00'*4
