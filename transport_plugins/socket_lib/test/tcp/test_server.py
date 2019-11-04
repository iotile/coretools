"""
Unit tests for WebSocket transport plugin - ws handler in gateway agent.
Also test that our WebSocketDeviceAdapter works well alone.
"""

import json
import pytest
import struct
import threading
from devices_factory import build_report_device, build_tracing_device, get_tracing_device_string


# Get traces sent from the config file
with open(get_tracing_device_string().split('@')[-1], "r") as conf_file:
    config = json.load(conf_file)
    traces_sent = config['device']['ascii_data']



@pytest.mark.parametrize('server', [build_report_device()], indirect=True)
def test_probe(device_adapter):
    scanned_devices = []

    def on_scan_callback(adapter, device, expiration_time):
        scanned_devices.append(device)

    device_adapter.add_callback('on_scan', on_scan_callback)

    result = device_adapter.probe_sync()
    assert result['success'] is True

    assert len(scanned_devices) == 1

    report_device = scanned_devices[0]
    assert report_device['uuid'] == 0x10
    assert report_device['connection_string'] == str(report_device['uuid'])


@pytest.mark.parametrize('server', [(build_report_device(), build_tracing_device())], indirect=True)
def test_device_adapter_connection(device_adapter):
    # Connect to the first device
    result = device_adapter.connect_sync(0, str(0x10))
    assert result['success'] is True

    # Try to connect to the same device (already connected)
    result = device_adapter.connect_sync(1, str(0x10))
    assert result['success'] is False

    # Connect to the second device
    result = device_adapter.connect_sync(1, str(0x11))
    assert result['success'] is True

    # Disconnect from a non existing device
    result = device_adapter.disconnect_sync(2)
    assert result['success'] is False

    # Disconnect from the first device
    result = device_adapter.disconnect_sync(0)
    assert result['success'] is True

    # Second device should be still connected
    result = device_adapter.connect_sync(2, str(0x11))
    assert result['success'] is False

    # Disconnect from a the second device
    result = device_adapter.disconnect_sync(1)
    assert result['success'] is True


@pytest.mark.skip(reason="Autoprobing is temporarily disabled")
@pytest.mark.parametrize('server', [build_report_device()], indirect=True)
@pytest.mark.parametrize('device_adapter', [{"autoprobe_interval": 0.1}], indirect=True)
def test_autoprobe(device_adapter):
    scanned_devices = []
    scan_complete = threading.Event()

    def on_scan_callback(adapter_id, device, expiration_time):
        assert adapter_id == device_adapter.id
        scanned_devices.append(device)
        scan_complete.set()

    device_adapter.add_callback('on_scan', on_scan_callback)

    flag = scan_complete.wait(timeout=5.0)
    assert flag is True
    assert len(scanned_devices) == 1

    report_device = scanned_devices[0]
    assert report_device['uuid'] == 0x10
    assert report_device['connection_string'] == str(report_device['uuid'])


@pytest.mark.parametrize('server', [build_tracing_device()], indirect=True)
def test_traces(device_adapter):
    result = {'traces': bytes()}
    traces_complete = threading.Event()

    def on_trace_callback(connection_id, trace):
        assert connection_id == 0
        result['traces'] += trace

        if len(result['traces']) >= len(traces_sent):
            traces_complete.set()

    device_adapter.add_callback('on_trace', on_trace_callback)

    device_adapter.connect_sync(0, str(0x11))
    device_adapter.open_interface_sync(0, 'tracing')

    flag = traces_complete.wait(timeout=5.0)
    assert flag is True
    assert result['traces'] == traces_sent.encode('utf-8')


@pytest.mark.parametrize('server', [build_report_device()], indirect=True)
def test_reports(device_adapter):
    reports = []
    reports_complete = threading.Event()

    def on_report_callback(connection_id, report):
        assert connection_id == 0
        reports.append(report)

        if len(reports) >= 3:
            reports_complete.set()

    device_adapter.add_callback('on_report', on_report_callback)

    device_adapter.connect_sync(0, str(0x10))
    device_adapter.open_interface_sync(0, 'streaming')

    flag = reports_complete.wait(timeout=5.0)
    assert flag is True
    assert len(reports) == 3


@pytest.mark.parametrize('server', [build_report_device()], indirect=True)
def test_send_rpc(device_adapter):
    device_adapter.connect_sync(0, str(0x10))
    device_adapter.open_interface_sync(0, 'rpc')

    result = device_adapter.send_rpc_sync(0, 120, 0xFFFF, bytes(), timeout=1.0)
    assert result['success'] is True
    assert result['status'] == 0xFF
    assert len(result['payload']) == 0

    payload = struct.pack('<H', 0)
    result = device_adapter.send_rpc_sync(0, 8, 0x200a, payload, timeout=1.0)
    assert result['success'] is True
    assert result['status'] == (1 << 7) | (1 << 6)
    assert len(result['payload']) > 0


@pytest.mark.parametrize('server', [build_report_device()], indirect=True)
def test_send_script(device_adapter):
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

    device_adapter.connect_sync(0, str(0x10))
    result = device_adapter.send_script_sync(0, script, on_progress_callback)

    assert result['success'] is True

    flag = script_complete.wait(5.0)
    assert flag is True
    assert progress['done'] > 0
