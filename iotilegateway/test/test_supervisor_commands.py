import pytest
from iotilegateway.supervisor import IOTileSupervisor, ServiceStatusClient

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


def test_send_rpc(supervisor):
    """Make sure we can send an RPC."""

    _visor, client1, _client2 = supervisor

    resp = client1.send_rpc('service_1', 0x8000, "")
    assert resp['result'] == 'service_not_found'

