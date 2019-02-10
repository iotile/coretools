"""Tests to ensure that our coroutine based emulation loop works."""

import pytest
import asyncio
from iotile.emulate.internal import EmulationLoop
from iotile.core.hw.virtual.common_types import AsynchronousRPCResponse
from iotile.core.exceptions import TimeoutExpiredError


def test_basic_eventloop():
    """Make sure basic things work."""

    def _rpc_executor(_address, rpc_id, arg_payload):
        if rpc_id == 0x8000:
            raise ValueError("Error")

        return arg_payload

    loop = EmulationLoop(_rpc_executor)
    loop.start()



    try:
        assert loop.call_rpc_external(8, 0x8001, b'abcd') == b'abcd'

        with pytest.raises(ValueError):
            loop.call_rpc_external(8, 0x8000, b'')

    finally:
        loop.stop()


def test_async_rpc():
    """Make sure we can send an asynchronous RPC."""
    loop = None

    def _rpc_executor(_address, rpc_id, arg_payload):
        if rpc_id == 0x8000:
            raise ValueError("Error")
        elif rpc_id == 0x8002:
            address, rpc_id = loop.get_current_rpc()
            asyncio.get_event_loop().call_soon(loop.finish_async_rpc, address, rpc_id, b'4444')
            raise AsynchronousRPCResponse()

        return arg_payload

    loop = EmulationLoop(_rpc_executor)
    loop.start()

    try:
        assert loop.call_rpc_external(8, 0x8001, b'abcd') == b'abcd'
        assert loop.call_rpc_external(8, 0x8002, b'abcd') == b'4444'
        loop.wait_idle()

    finally:
        loop.stop()


def test_rpc_timeout():
    """Make sure we can timeout an RPC."""

    def _rpc_executor(_address, rpc_id, arg_payload):
        raise AsynchronousRPCResponse()

    loop = EmulationLoop(_rpc_executor)
    loop.start()

    try:
        with pytest.raises(TimeoutExpiredError):
            loop.call_rpc_external(8, 0x8001, b'abcd', timeout=0.001)

        with pytest.raises(TimeoutExpiredError):
            loop.wait_idle(timeout=0.001)

    finally:
        loop.stop()
