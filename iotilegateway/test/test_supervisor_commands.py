"""Tests to make sure IOTileSupervisor and RPC dispatching work."""

import pytest
import struct
import json
from iotile.core.hw.virtual import RPCDispatcher, tile_rpc
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.hw.proxy.proxy import TileBusProxyObject
from iotilegateway.supervisor import IOTileSupervisor, ServiceStatusClient


class BasicRPCDispatcher(RPCDispatcher):
    @tile_rpc(0x8000, "LL", "L")
    def add(self, arg1, arg2):
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


@pytest.fixture(scope="function")
def linked_tile(rpc_agent, tmpdir):
    """Create a connected HardwareManager instance with a proxy pointed at an RPCDispatcher."""

    visor, _client1, _client2 = rpc_agent

    # Create a config file that we can use to initialize a virtual device that will point at our
    # BasicRPCDispatch via a running IOTileSupervisor.  Currently, HardwareManager can only
    # load configurations for virtual devices from actual files, so we need to save this to a
    # temp file.
    config = {
        "device": {
            "iotile_id": 1,
            "tiles": [
                {
                    "name": "service_delegate",
                    "address": 11,
                    "args": {
                        "url": "ws://127.0.0.1:%d/services" % visor.port, # This has to match the port of the supervisor instance that we want to connect to
                        "service": "service_1",      # This has to match the service name that the RPCDispatcher is registered as an agent for
                        "name": "bsctst"             # This is the 6 character string that must match the ModuleName() of the proxy and is used to find the right proxy
                    }
                }
            ]
        }
    }

    # This is a special py.path.local object from pytest
    # https://docs.pytest.org/en/latest/tmpdir.html
    config_path_obj = tmpdir.join('config.json')
    config_path_obj.write(json.dumps(config))

    config_path = str(config_path_obj)

    # This will create a HardwareManager pointed at a virtual tile based device
    # where the tiles that are added to the virtual device are found using the config
    # file specified after the @ symbol.
    hw = HardwareManager(port="virtual:tile_based@%s" % config_path)  # pylint:disable=invalid-name; We use hw throughout CoreTools to denote a HardwareManager instance

    # We specified that the virtual device should be at uuid 1 (using iotile_id above)
    # so we know how to connect to it.  We also know that we specified a single tile
    # at address 11 inside that virtual device so we will be able to get its proxy
    # object by calling hw.get(11) once we are connected.
    hw.connect(1)
    yield hw

    hw.disconnect()


def test_service_delegate_tile(linked_tile):
    """Make sure our service delegate tile works correctly."""

    hw = linked_tile  # pylint:disable=invalid-name; We use hw throughout CoreTools to denote a HardwareManager instance

    # Normally this is not required but since we are conecting to a
    # virtual tile that doesn't have a known proxy ('bsctst'), we need
    # to temporarily register the proxy that we would like to use othweise
    # we will get a:
    #  HardwareError: HardwareError: Could not find proxy object for tile
    #    Additional Information:
    #     - known_names: ['Simple', 'NO APP']
    #     - name: 'bsctst'
    HardwareManager.RegisterDevelopmentProxy(BasicRPCDispatcherProxy)

    # When we call get(address) the HardwareManager will ask the tile at that address,
    # in this case the ServiceDelegateTile what it's 6 character name is.  It will
    # return, in this case 'bsctst' because that's what we put in the config.json
    # file we created in the linked_tile fixture.  The HardwareManager will then
    # look up in its dictionary of known proxies for one whose ModuleName() exactly
    # matches and return that object.

    proxy = hw.get(11)

    result = proxy.add(5, 1)
    assert result == 5 + 1


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


def test_send_rpc_not_found(supervisor):
    """Make sure we RPCs get forwarded and timeout when not answered."""

    _visor, client1, client2 = supervisor

    client1.register_agent('service_1')
    resp = client2.send_rpc('service_1', 0x8000, "")
    assert resp['result'] == 'rpc_not_found'


def test_send_rpc_success(rpc_agent):
    """Make sure we can send RPCs that are implemented."""

    _visor, client1, client2 = rpc_agent

    resp = client2.send_rpc('service_1', 0x8000, b'\x00'*8)
    assert resp['result'] == 'success'
    assert resp['response'] == b'\x00'*4


def test_send_rpc_execution(rpc_agent):
    """Make sure we can send RPCs that are implemented."""

    _visor, client1, client2 = rpc_agent

    args = struct.pack("<LL", 1, 2)

    resp = client2.send_rpc('service_1', 0x8000, args)
    assert resp['result'] == 'success'

    arg_sum, = struct.unpack("<L", resp['response'])
    assert arg_sum == 3


def test_send_rpc_invalid_args(rpc_agent):
    """Make sure an exception gets thrown when an RPC has invalid args."""

    _visor, client1, client2 = rpc_agent

    args = struct.pack("<LLL", 1, 2, 3)

    resp = client2.send_rpc('service_1', 0x8000, args)
    assert resp['result'] == 'invalid_arguments'


def test_send_rpc_exception(rpc_agent):
    """Make sure an exception gets thrown when an RPC has an error processing."""

    _visor, client1, client2 = rpc_agent

    resp = client2.send_rpc('service_1', 0x8001, b'')
    assert resp['result'] == 'execution_exception'


def test_send_rpc_invalid_response(rpc_agent):
    """Make sure an exception gets thrown when an RPC returns a nonconforming response."""

    _visor, client1, client2 = rpc_agent

    resp = client2.send_rpc('service_1', 0x8002, b'')
    assert resp['result'] == 'invalid_response'
