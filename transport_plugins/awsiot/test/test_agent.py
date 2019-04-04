import pytest
import queue

from iotile_transport_awsiot.mqtt_client import OrderedAWSIOTClient
import time

pytestmark = pytest.mark.skip("This distribution needs to be updated to work with asyncio gateway")


def test_gateway(gateway, local_broker, args):
    """Make sure we can connect to the gateway by sending packets over the mqtt message broker."""

    client = OrderedAWSIOTClient(args)
    client.connect('hello')
    local_broker.expect(5)
    client.publish('devices/d--0000-0000-0000-0002/control/probe', {'type': 'command', 'operation': 'probe', 'client': 'hello'})
    local_broker.wait()

    # There should be 1 command message, 1 response and 1 advertisement notification per device
    assert len(local_broker.messages) == 5

    assert 'devices/d--0000-0000-0000-0002/devices/d--0000-0000-0000-0001/data/advertisement' in local_broker.messages
    assert 'devices/d--0000-0000-0000-0002/devices/d--0000-0000-0000-0003/data/advertisement' in local_broker.messages
    assert 'devices/d--0000-0000-0000-0002/devices/d--0000-0000-0000-0004/data/advertisement' in local_broker.messages
    assert 'devices/d--0000-0000-0000-0002/data/status' in local_broker.messages
    assert 'devices/d--0000-0000-0000-0002/control/probe' in local_broker.messages


def test_probe(gateway, hw_man, local_broker):
    """Make sure we can probe for devices."""

    local_broker.expect(3)
    results = hw_man.scan(wait=0.1)

    assert len(results) == 3
    assert results[0]['uuid'] == 1
    assert results[0]['connection_string'] == 'd--0000-0000-0000-0001'
    assert results[1]['uuid'] == 3
    assert results[1]['connection_string'] == 'd--0000-0000-0000-0003'
    assert results[2]['uuid'] == 4
    assert results[2]['connection_string'] == 'd--0000-0000-0000-0004'


def test_connect(gateway, hw_man, local_broker):
    """Make sure we can connect to a device."""

    hw_man.scan(wait=0.1)
    hw_man.connect(1)
    hw_man.disconnect()


def test_streaming(gateway, hw_man, local_broker):
    """Make sure we can receive streamed data."""

    hw_man.connect(3, wait=0.1)
    hw_man.enable_streaming()
    reps = hw_man.wait_reports(100, timeout=1.0)

    assert len(reps) == 100


def test_tracing(gateway, hw_man, local_broker):
    """Make sure we can receive tracing data."""

    hw_man.connect(4, wait=0.1)
    hw_man.enable_tracing()

    time.sleep(0.1)
    data = hw_man.dump_trace('raw')
    assert data == b'Hello world, this is tracing data!'


def test_rpcs(gateway, hw_man, local_broker):
    """Make sure we can send rpcs."""

    hw_man.connect(3, wait=0.1)
    hw_man.controller()

def test_script(gateway, hw_man, local_broker):
    """Make sure we can send scripts."""

    script = bytearray(('ab'*10000).encode('utf-8'))
    progs = queue.Queue()
    hw_man.connect(3, wait=0.1)

    gateway.agents[0].throttle_progress = 0.0
    hw_man.stream._send_highspeed(script, lambda x, y: progs.put((x,y)))

    last_done = -1
    last_total = None
    prog_count = 0
    while not progs.empty():
        done, total = progs.get(block=False)
        assert done <= total
        assert done >= last_done
        if last_total is not None:
            assert total == last_total

        last_done = done
        last_total = total
        prog_count += 1

    assert prog_count > 0

    dev = gateway.device_manager.adapters[0]._adapter.devices[3]
    assert dev.script == script


def test_script_chunking(gateway, hw_man, local_broker):
    """Make sure we can send scripts."""

    script = bytearray(('a'*1024*80).encode('utf-8'))
    progs = queue.Queue()
    hw_man.connect(3, wait=0.1)

    gateway.agents[0].throttle_progress = 0.0
    hw_man.stream._send_highspeed(script, lambda x, y: progs.put((x, y)))

    last_done = -1
    last_total = None
    prog_count = 0
    while not progs.empty():
        done, total = progs.get(block=False)
        assert done <= total
        assert done >= last_done
        if last_total is not None:
            assert total == last_total

        last_done = done
        last_total = total

        prog_count += 1

    assert prog_count > 0

    dev = gateway.device_manager.adapters[0]._adapter.devices[3]
    assert dev.script == script


def test_script_progress_throttling(gateway, hw_man, local_broker):
    """Make sure progress updates are properly throttled."""

    script = bytearray(('a'*1024*80).encode('utf-8'))
    progs = []
    hw_man.connect(3, wait=0.1)

    gateway.agents[0].throttle_progress = 10.0
    hw_man.stream._send_highspeed(script, lambda x, y: progs.append((x, y)))

    dev = gateway.device_manager.adapters[0]._adapter.devices[3]
    assert dev.script == script

    # This should happen faster than our throttling period so we should
    # get exactly 2 progress updates, on start and on finish
    assert len(progs) == 2
    x, y = progs[0]

    assert x == 0

    x, y = progs[1]
    assert x == y

def test_autodisconnect(gateway, hw_man, local_broker):
    """Make sure we autodisconnect clients."""

    gateway.agents[0].client_timeout = 0.1

    hw_man.connect(3, wait=0.1)
    assert len(gateway.agents[0]._connections) == 1

    time.sleep(1.5)

    assert len(gateway.agents[0]._connections) == 0

    assert hw_man.stream.connection_interrupted is True

    # Make sure we can reconnect automatically
    hw_man.controller()
    assert len(gateway.agents[0]._connections) == 1

    # Let us lapse again
    time.sleep(1.5)
    assert len(gateway.agents[0]._connections) == 0

    # Return to our disconnected state
    hw_man.disconnect()

    # Make sure we can connect normally again
    hw_man.connect(3, wait=0.1)
