"""Test the StandardDeviceServer class."""

import pytest
from iotile.core.utilities import BackgroundEventLoop
from iotile.core.hw.transport import StandardDeviceServer, VirtualDeviceAdapter
from iotile.core.hw.exceptions import DeviceAdapterError, DeviceServerError
from iotile.core.hw.virtual import TileNotFoundError
from iotile.mock.devices import ReportTestDevice, TracingTestDevice

class BasicDeviceServer(StandardDeviceServer):
    """Minimal subclass of device server for testing."""

    async def start(self):
        pass


@pytest.fixture(scope="function")
def server():
    """A clean device server."""
    shared_events = []

    async def _event_callback(client_id, event_tuple, user_data):
        shared_events.append((client_id, event_tuple))

    loop = BackgroundEventLoop()

    report_dev = ReportTestDevice({
        'iotile_id': 1
    })

    tracing_dev = TracingTestDevice({
        'iotile_id': 2
    })

    adapter = VirtualDeviceAdapter(None, devices=[report_dev, tracing_dev], loop=loop)
    server = BasicDeviceServer(adapter, loop=loop)
    server.client_event_handler = _event_callback

    loop.start()
    loop.run_coroutine(adapter.start())
    loop.run_coroutine(server.start())

    yield loop, shared_events, server, adapter

    try:
        loop.run_coroutine(server.stop())
        loop.run_coroutine(adapter.stop())
    finally:
        loop.stop()


def test_basic_probe(server):
    """Make sure we can scan through a DeviceServer."""

    loop, events, server, _ = server

    client_id = server.setup_client()

    assert len(events) == 0
    assert isinstance(client_id, str)

    loop.run_coroutine(server.probe(client_id))
    assert len(events) == 2

    event_client, (_, name, event) = events[0]
    assert event_client == client_id
    assert name == "device_seen"
    assert isinstance(event, dict)

    with pytest.raises(DeviceServerError):
        loop.run_coroutine(server.probe("random client id"))

    # Make sure it works repeatedly
    loop.run_coroutine(server.probe(client_id))
    assert len(events) == 4


def test_multiclient_probe(server):
    """Make sure multiple clients can probe separately."""

    loop, events, server, _ = server

    client1 = server.setup_client()
    client2 = server.setup_client()

    loop.run_coroutine(server.probe(client1))
    loop.run_coroutine(server.probe(client2))

    assert len(events) == 8


def test_connect(server):
    """Make sure we can connect to a device."""

    loop, _, server, _ = server

    client1 = server.setup_client()
    client2 = server.setup_client()

    loop.run_coroutine(server.connect(client1, '1'))

    with pytest.raises(DeviceAdapterError):
        loop.run_coroutine(server.connect(client2, '1'))

    with pytest.raises(DeviceServerError):
        loop.run_coroutine(server.disconnect(client2, '1'))

    loop.run_coroutine(server.disconnect(client1, '1'))
    loop.run_coroutine(server.connect(client2, '1'))


def test_multiclient_connect(server):
    """Make sure multiple clients can connect to multiple devices."""

    loop, events, server, _ = server

    client1 = server.setup_client()
    client2 = server.setup_client()

    loop.run_coroutine(server.connect(client1, '1'))
    loop.run_coroutine(server.connect(client2, '2'))

    loop.run_coroutine(server.open_interface(client1, '1', 'streaming'))
    loop.run_coroutine(server.open_interface(client2, '2', 'tracing'))

    assert any(x[0] == client1 for x in events)
    assert any(x[0] == client2 for x in events)

    with pytest.raises(DeviceServerError):
        loop.run_coroutine(server.open_interface(client1, '2', 'streaming'))

    with pytest.raises(DeviceServerError):
        loop.run_coroutine(server.open_interface(client2, '1', 'tracing'))


def test_send_rpc(server):
    """Make sure we can send RPCs."""

    loop, _, server, _ = server

    client1 = server.setup_client()

    with pytest.raises(DeviceServerError):
        loop.run_coroutine(server.send_rpc(client1, '1', 1, 0xabcd, b'', timeout=0.1))

    loop.run_coroutine(server.connect(client1, '1'))

    with pytest.raises(TileNotFoundError):
        loop.run_coroutine(server.send_rpc(client1, '1', 1, 0xabcd, b'', timeout=0.1))


def test_send_script(server):
    """Make sure we can send scripts."""

    loop, events, server, _ = server

    client1 = server.setup_client()

    with pytest.raises(DeviceServerError):
        loop.run_coroutine(server.send_script(client1, '1', bytes(100)))

    loop.run_coroutine(server.connect(client1, '1'))
    loop.run_coroutine(server.send_script(client1, '1', bytes(100)))

    assert len(events) > 0
    assert all(x[1][1] == 'progress' for x in events)


def test_all_interfaces(server):
    """Make sure we can open and close all interfaces."""

    loop, _, server, _ = server

    client1 = server.setup_client()

    loop.run_coroutine(server.connect(client1, '1'))

    loop.run_coroutine(server.open_interface(client1, '1', 'streaming'))
    loop.run_coroutine(server.close_interface(client1, '1', 'streaming'))

    loop.run_coroutine(server.open_interface(client1, '1', 'tracing'))
    loop.run_coroutine(server.close_interface(client1, '1', 'tracing'))

    loop.run_coroutine(server.open_interface(client1, '1', 'rpc'))
    loop.run_coroutine(server.close_interface(client1, '1', 'rpc'))

    loop.run_coroutine(server.open_interface(client1, '1', 'script'))
    loop.run_coroutine(server.close_interface(client1, '1', 'script'))

    loop.run_coroutine(server.open_interface(client1, '1', 'debug'))
    loop.run_coroutine(server.close_interface(client1, '1', 'debug'))


def test_receive_reports(server):
    """Make sure we get report events."""

    loop, events, server, _ = server

    client1 = server.setup_client()
    _client2 = server.setup_client()

    loop.run_coroutine(server.connect(client1, '1'))
    loop.run_coroutine(server.open_interface(client1, '1', 'streaming'))

    # Make sure client1 and only client1 gets reports
    assert len(events) > 0
    assert all(x[1][1] == 'report' for x in events)
    assert all(x[0] == client1 for x in events)

    len_1 = len(events)

    loop.run_coroutine(server.close_interface(client1, '1', 'streaming'))
    loop.run_coroutine(server.open_interface(client1, '1', 'streaming'))

    # Make sure we got more events the second time.
    assert len(events) > len_1

def test_receive_traces(server):
    """Make sure we get trace events."""

    loop, events, server, _ = server

    client1 = server.setup_client()
    _client2 = server.setup_client()

    loop.run_coroutine(server.connect(client1, '2'))
    loop.run_coroutine(server.open_interface(client1, '2', 'tracing'))

    # Make sure client1 and only client1 gets reports
    assert len(events) > 0
    assert all(x[1][1] == 'trace' for x in events)
    assert all(x[0] == client1 for x in events)
