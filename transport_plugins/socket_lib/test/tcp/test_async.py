"""Test ValidateWSCient against ValidatingWSServer."""

import pytest
import threading
from iotile.core.exceptions import ExternalError
from iotile.core.utilities.async_tools import BackgroundEventLoop
from iotile_transport_socket_lib.unix_socket.unixsocket_implementation import UnixServerImplementation
from iotile_transport_socket_lib.unix_socket.unixsocket_implementation import UnixClientImplementation
from iotile_transport_socket_lib.generic import AsyncSocketServer, AsyncSocketClient
from iotile.core.utilities.schema_verify import Verifier, StringVerifier, IntVerifier

@pytest.fixture(scope="function")
def client_server(tmp_path):
    """Create a connected async ws client and server pair."""

    loop = BackgroundEventLoop()
    loop.start()
    socketfile = str((tmp_path / "socket").resolve())

    server = None
    client = None
    try:

        socket_implementation = UnixServerImplementation(path=socketfile, loop=loop)
        server = AsyncSocketServer(socket_implementation, loop=loop)
        loop.run_coroutine(server.start())

        client_implementation = UnixClientImplementation(path=socketfile, loop=loop)
        client = AsyncSocketClient(client_implementation, loop=loop)
        loop.run_coroutine(client.start())

        yield loop, client, server
    finally:
        if client is not None:
            loop.run_coroutine(client.stop())

        if server is not None:
            loop.run_coroutine(server.stop())

        loop.stop()


def test_basic(client_server):
    """Make sure client/server work at a basic level."""

    loop, client, _ = client_server

    with pytest.raises(ExternalError):
        loop.run_coroutine(client.send_command('test_cmd', dict(abc=False), None, timeout=1))


def test_parallel_operations(client_server):
    """Make sure operations run in parallel.

    This unit test will deadlock if parallel operations are not supported.
    """

    loop, client, server = client_server

    event = loop.create_event()

    async def _set_event(payload, context):
        event.set()

    async def _wait_event(payload, context):
        await event.wait()

    server.register_command('set', _set_event, Verifier())
    server.register_command('wait', _wait_event, Verifier())

    async def deadlock_if_not_parallel():
        wait_task = loop.add_task(client.send_command('wait', {}, Verifier(), timeout=1))
        set_task = loop.add_task(client.send_command('set', {}, Verifier(), timeout=1))

        await wait_task.task
        await set_task.task

    loop.run_coroutine(deadlock_if_not_parallel())


def test_event_sending(client_server):
    """Make sure we can send and receive events."""

    loop, client, server = client_server

    shared = [0]
    async def _send_event(payload, context):
        server = context.server
        con = context.connection

        await server.send_event(con, payload, 5)

    def event_callback(payload):
        shared[0] += payload

    server.register_command('send_event', _send_event, StringVerifier())

    client.register_event('event1', event_callback, IntVerifier())

    loop.run_coroutine(client.send_command('send_event', 'event1', Verifier()))
    assert shared[0] == 5

    loop.run_coroutine(client.send_command('send_event', 'event1', Verifier()))
    assert shared[0] == 10

    loop.run_coroutine(client.send_command('send_event', 'event2', Verifier()))
    assert shared[0] == 10
