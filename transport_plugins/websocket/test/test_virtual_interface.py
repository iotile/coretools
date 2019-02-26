"""
Unit tests for WebSocket transport plugin - virtual interface.
Also test that our WebSocketDeviceAdapter works well with the HardwareManager.
"""

import json
import pytest
import queue
from devices_factory import build_report_device, build_tracing_device, get_tracing_device_string


tracing_device_string = get_tracing_device_string()

# Get traces sent from the config file
with open(tracing_device_string.split('@')[-1], "r") as conf_file:
    config = json.load(conf_file)
    traces_sent = config['device']['ascii_data']


@pytest.mark.parametrize('virtual_interface', [build_report_device()], indirect=True)
def test_probe(hw):
    devices = hw.scan()

    assert isinstance(devices, list)
    assert len(devices) == 1

    report_device = devices[0]
    assert report_device['uuid'] == 0x10
    assert report_device['connection_string'] == str(report_device['uuid'])


@pytest.mark.parametrize('virtual_interface', [build_report_device()], indirect=True)
def test_hw_connection(hw, virtual_interface):
    _, interface = virtual_interface

    assert interface.device is not None
    assert interface.device.connected is False

    hw.connect(0x10)
    assert interface.device.connected is True

    hw.disconnect()
    assert interface.device.connected is False

    hw.connect(0x10)
    assert interface.device.connected is True


@pytest.mark.parametrize('virtual_interface', [build_tracing_device()], indirect=True)
def test_traces(hw, virtual_interface):
    hw.connect(0x11)

    _, interface = virtual_interface
    assert interface.tracing_enabled is False

    hw.enable_tracing()
    assert interface.tracing_enabled is True

    raw_received_traces = hw.wait_trace(len(traces_sent), timeout=5.0)

    assert raw_received_traces == traces_sent.encode('utf-8')


@pytest.mark.parametrize('virtual_interface', [build_report_device()], indirect=True)
def test_reports(hw, virtual_interface):
    hw.connect(0x10)

    _, interface = virtual_interface
    assert hw.count_reports() == 0
    assert interface.streaming_enabled is False

    hw.enable_streaming()
    assert interface.streaming_enabled is True

    reports = hw.wait_reports(3, timeout=5.0)
    assert len(reports) == 3


@pytest.mark.parametrize('virtual_interface', [build_report_device()], indirect=True)
def test_send_rpc(hw):
    hw.connect(0x10)
    con = hw.controller()
    assert con is not None


@pytest.mark.parametrize('virtual_interface', [build_report_device()], indirect=True)
def test_send_script(hw, virtual_interface):
    hw.connect(0x10)

    _, interface = virtual_interface

    script = bytes(b'ab')*100
    progs = queue.Queue()

    hw.stream._send_highspeed(script, lambda x, y: progs.put((x, y)))

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
