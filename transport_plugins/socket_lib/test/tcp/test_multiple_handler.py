"""
Unit tests for WebSocket transport plugin - ws handler in multiple gateways.
One of the gateway is used as an intermediate. Useful to test multiple connections.
"""

import json
import struct
import threading
import pytest
from devices_factory import build_report_device, build_tracing_device, get_tracing_device_string

tracing_device_string = get_tracing_device_string()

# Get traces sent from the config file
with open(tracing_device_string.split('@')[-1], "r") as conf_file:
    config = json.load(conf_file)
    traces_sent = config['device']['ascii_data']


@pytest.mark.parametrize('server', [(build_report_device(), build_tracing_device())], indirect=True)
def test_probe(multiple_device_adapter):
    device_adapter1, _ = multiple_device_adapter
    scanned_devices = []

    def on_scan_callback(adapter, device, expiration_time):
        scanned_devices.append(device)

    device_adapter1.add_callback('on_scan', on_scan_callback)

    result = device_adapter1.probe_sync()
    assert result['success'] is True

    assert len(scanned_devices) == 2

    report_device = scanned_devices[0]
    assert report_device['uuid'] == 0x10
    assert report_device['connection_string'] == str(report_device['uuid'])


@pytest.mark.parametrize('server', [(build_report_device(), build_tracing_device())], indirect=True)
def test_multiple_device_adapter_connection(multiple_device_adapter):
    device_adapter1, device_adapter2 = multiple_device_adapter

    # Connect to the first device
    result = device_adapter1.connect_sync(0, str(0x10))
    assert result['success'] is True

    # Try to connect to the same device (already connected) via the second device adapter
    result = device_adapter2.connect_sync(1, str(0x10))
    assert result['success'] is False

    # Connect to the second device via the second device adapter
    result = device_adapter2.connect_sync(1, str(0x11))
    assert result['success'] is True

    # Disconnect from the wrong device adapter
    result = device_adapter1.disconnect_sync(1)
    assert result['success'] is False

    # Disconnect from the first device
    result = device_adapter1.disconnect_sync(0)
    assert result['success'] is True

    # Second device should be still connected
    result = device_adapter1.connect_sync(2, str(0x11))
    assert result['success'] is False

    # Disconnect from a the second device
    result = device_adapter2.disconnect_sync(1)
    assert result['success'] is True


@pytest.mark.parametrize('server', [(build_report_device(), build_tracing_device())], indirect=True)
def test_traces(multiple_device_adapter):
    device_adapter1, device_adapter2 = multiple_device_adapter

    result = {'traces': bytes()}
    traces_complete = threading.Event()

    def on_trace_callback(connection_id, trace):
        assert connection_id == 0
        result['traces'] += trace

        if len(result['traces']) >= len(traces_sent):
            traces_complete.set()

    device_adapter1.add_callback('on_trace', on_trace_callback)

    device_adapter1.connect_sync(0, str(0x11))
    device_adapter2.connect_sync(0, str(0x10))
    device_adapter1.open_interface_sync(0, 'tracing')

    flag = traces_complete.wait(timeout=5.0)
    assert flag is True
    assert result['traces'] == traces_sent.encode('utf-8')


@pytest.mark.parametrize('server', [(build_report_device(), build_tracing_device())], indirect=True)
def test_reports(multiple_device_adapter):
    device_adapter1, device_adapter2 = multiple_device_adapter
    reports = []
    reports_complete = threading.Event()

    def on_report_callback(connection_id, report):
        assert connection_id == 0
        reports.append(report)

        if len(reports) >= 3:
            reports_complete.set()

    device_adapter1.add_callback('on_report', on_report_callback)

    device_adapter1.connect_sync(0, str(0x10))
    device_adapter2.connect_sync(0, str(0x11))
    device_adapter1.open_interface_sync(0, 'streaming')

    flag = reports_complete.wait(timeout=5.0)
    assert flag is True
    assert len(reports) == 3


@pytest.mark.parametrize('server', [(build_report_device(), build_tracing_device())], indirect=True)
def test_send_rpc(multiple_device_adapter):
    device_adapter1, device_adapter2 = multiple_device_adapter
    device_adapter1.connect_sync(0, str(0x10))
    device_adapter2.connect_sync(0, str(0x11))
    device_adapter1.open_interface_sync(0, 'rpc')
    device_adapter2.open_interface_sync(0, 'rpc')

    result = device_adapter1.send_rpc_sync(0, 120, 0xFFFF, bytes(), timeout=1.0)
    assert result['success'] is True
    assert result['status'] == 0xFF
    assert len(result['payload']) == 0

    payload = struct.pack('<H', 0)
    result = device_adapter2.send_rpc_sync(0, 8, 0x200a, payload, timeout=1.0)
    assert result['success'] is True
    assert result['status'] == (1 << 1)
    assert len(result['payload']) == 0

    payload = struct.pack('<H', 0)
    result = device_adapter1.send_rpc_sync(0, 8, 0x200a, payload, timeout=1.0)
    assert result['success'] is True
    assert result['status'] == (1 << 7) | (1 << 6)
    assert len(result['payload']) > 0


@pytest.mark.parametrize('server', [(build_report_device(), build_tracing_device())], indirect=True)
def test_send_script(multiple_device_adapter):
    device_adapter1, device_adapter2 = multiple_device_adapter
    progress = {'done': 0, 'total': None}
    script_complete = threading.Event()

    def on_progress_callback(done_count, total_count):
        if progress['total'] is not None:
            assert progress['total'] == total_count

        assert done_count >= progress['done']
        assert done_count <= total_count

        progress['total'] = total_count
        progress['done'] = done_count

        if done_count == total_count:
            script_complete.set()

    script = bytes(b'ab')*100

    device_adapter1.connect_sync(0, str(0x10))
    device_adapter2.connect_sync(0, str(0x11))
    result = device_adapter1.send_script_sync(0, script, on_progress_callback)

    assert result['success'] is True

    flag = script_complete.wait(5.0)
    assert flag is True
    assert progress['done'] > 0
