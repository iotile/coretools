"""Tests to make sure IOTileSupervisor and RPC dispatching work with an asyncio ServiceStatusClient."""

import struct


def test_send_rpc_unknown(loop, async_supervisor):
    """Make sure we can send an RPC at a basic level."""

    visor, client1 = async_supervisor

    resp = loop.run_coroutine(client1.send_rpc('service1', 0x8000, b""))
    assert resp == dict(result='service_not_found', response=b'')

    # Make sure everything was cleaned up
    assert len(visor.service_manager.rpc_results) == 0
    assert len(visor.service_manager.in_flight_rpcs) == 0

def test_register_agent(loop, async_supervisor):
    """Make sure we can register as an agent."""

    visor, client1 = async_supervisor

    assert len(visor.service_manager.agents) == 0
    loop.run_coroutine(client1.register_agent('service1'))

    assert len(visor.service_manager.agents) == 1
    assert 'service1' in visor.service_manager.agents


def test_send_rpc_not_found(loop, rpc_supervisor):
    """Make sure we get an error when an RPC is not found."""

    _visor, async_client, sync_client = rpc_supervisor

    resp = loop.run_coroutine(async_client.send_rpc('service1', 0x9000, b""))
    assert resp['result'] == 'rpc_not_found'

    resp2 = sync_client.send_rpc('service1', 0x9000, b"")
    assert resp2 == resp


def test_send_rpc_success(loop, rpc_supervisor):
    """Make sure we can send RPCs that are implemented."""

    _visor, async_client, sync_client = rpc_supervisor


    resp = loop.run_coroutine(async_client.send_rpc('service1', 0x8000, b'\x00'*8))
    assert resp['result'] == 'success'
    assert resp['response'] == b'\x00'*4

    resp2 = sync_client.send_rpc('service1', 0x8000, b'\x00'*8)
    assert resp2 == resp


def test_send_rpc_execution(loop, rpc_supervisor):
    """Make sure we can send RPCs that are implemented."""

    _visor, async_client, sync_client = rpc_supervisor

    args = struct.pack("<LL", 1, 2)

    resp = loop.run_coroutine(async_client.send_rpc('service1', 0x8000, args))
    assert resp['result'] == 'success'

    arg_sum, = struct.unpack("<L", resp['response'])
    assert arg_sum == 3

    resp2 = sync_client.send_rpc('service1', 0x8000, args)
    assert resp2 == resp


def test_send_rpc_invalid_args(loop, rpc_supervisor):
    """Make sure an exception gets thrown when an RPC has invalid args."""

    _visor, async_client, sync_client = rpc_supervisor

    args = struct.pack("<LLL", 1, 2, 3)

    resp = loop.run_coroutine(async_client.send_rpc('service1', 0x8000, args))
    assert resp['result'] == 'invalid_arguments'

    resp2 = sync_client.send_rpc('service1', 0x8000, args)
    assert resp2 == resp


def test_send_rpc_exception(loop, rpc_supervisor):
    """Make sure an exception gets thrown when an RPC has an error processing."""

    _visor, async_client, sync_client = rpc_supervisor

    resp = loop.run_coroutine(async_client.send_rpc('service1', 0x8001, b''))
    assert resp['result'] == 'execution_exception'

    resp2 = sync_client.send_rpc('service1', 0x8001, b'')
    assert resp2 == resp


def test_send_rpc_invalid_response(loop, rpc_supervisor):
    """Make sure an exception gets thrown when an RPC returns a nonconforming response."""

    _visor, async_client, sync_client = rpc_supervisor

    resp = loop.run_coroutine(async_client.send_rpc('service1', 0x8002, b''))
    assert resp['result'] == 'invalid_response'

    resp2 = sync_client.send_rpc('service1', 0x8002, b'')
    assert resp2 == resp
