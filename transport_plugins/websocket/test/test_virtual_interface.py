"""Unit tests for WebSocket transport plugin - virtual interface."""

import pytest
import queue
from devices_factory import build_report_device, build_tracing_device

text = """Hello world! How are you? Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer lobortis egestas
mollis. Donec a sapien sed quam pulvinar faucibus. Nullam sed finibus urna. Quisque vehicula eros sit amet lacus rutrum
rutrum. Duis non laoreet est. Fusce gravida suscipit quam nec lacinia. Aliquam eget condimentum orci. Aliquam at
convallis ipsum. Nulla at lacus quis metus luctus laoreet id vel est. Good bye!"""


@pytest.mark.parametrize('virtual_interface', [build_report_device(0x10)], indirect=True)
def test_probe(hw):
    devices = hw.scan()

    assert isinstance(devices, list)
    assert len(devices) == 1

    report_device = devices[0]

    assert report_device['uuid'] == 0x10
    assert report_device['connection_string'] == str(report_device['uuid'])


@pytest.mark.parametrize('virtual_interface', [build_report_device(0x10)], indirect=True)
def test_hw_connection(hw, virtual_interface):
    _, interface = virtual_interface

    assert interface.device is not None
    assert interface.device.connected is False

    hw.connect(0x10)
    assert interface.device.connected is True

    hw.disconnect()
    assert interface.device.connected is False


@pytest.mark.parametrize('virtual_interface', [build_tracing_device(0x10, text)], indirect=True)
@pytest.mark.parametrize('connected_hw', [0x10], indirect=True)
def test_traces(connected_hw, virtual_interface):
    _, interface = virtual_interface
    assert interface.tracing_enabled is False

    connected_hw.enable_tracing()
    assert interface.tracing_enabled is True

    raw_received_traces = connected_hw.wait_trace(len(text), timeout=5.0)

    assert raw_received_traces == text.encode('utf-8')


@pytest.mark.parametrize('virtual_interface', [build_report_device(0x10)], indirect=True)
@pytest.mark.parametrize('connected_hw', [0x10], indirect=True)
def test_reports(connected_hw, virtual_interface):
    _, interface = virtual_interface
    assert connected_hw.count_reports() == 0
    assert interface.streaming_enabled is False

    connected_hw.enable_streaming()
    assert interface.streaming_enabled is True

    reports = connected_hw.wait_reports(3, timeout=5.0)
    assert len(reports) == 3


@pytest.mark.parametrize('virtual_interface', [build_report_device(0x10)], indirect=True)
@pytest.mark.parametrize('connected_hw', [0x10], indirect=True)
def test_send_rpc(connected_hw):
    con = connected_hw.controller()
    assert con is not None


@pytest.mark.parametrize('virtual_interface', [build_report_device(0x10)], indirect=True)
@pytest.mark.parametrize('connected_hw', [0x10], indirect=True)
def test_send_script(connected_hw, virtual_interface):
    _, interface = virtual_interface

    script = bytes(b'ab')*100
    progs = queue.Queue()

    connected_hw.stream._send_highspeed(script, lambda x, y: progs.put((x, y)))

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

    assert interface.device.script == script

# TODO: write tests for real gateway agent: add multiple connections tests + adapt base64 in gateway agent
