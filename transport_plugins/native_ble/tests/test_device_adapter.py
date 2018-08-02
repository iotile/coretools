"""
Unit tests for native BLE transport plugin - tests of the NativeBLEDeviceAdapter.
"""

import pytest
import struct
import threading
import time
from bable_interface import Controller
from iotile.core.exceptions import ExternalError
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.hw.reports import BroadcastReport, IOTileReading, IndividualReadingReport
from iotile_transport_native_ble.device_adapter import NativeBLEDeviceAdapter
from iotile_transport_native_ble.tilebus import *


def test_start_stop(mock_bable):
    """Test if device adapter starts and stops correctly."""
    device_adapter = NativeBLEDeviceAdapter(port=None)

    # Test if it has been started
    assert mock_bable.counters['start'] > 0
    assert device_adapter.stopped is False

    num_stop_bable = mock_bable.counters['stop']  # To count number of calls to bable_interface stop function

    device_adapter.stop_sync()
    # Test if it has been stopped
    assert mock_bable.counters['stop'] == num_stop_bable + 1
    assert device_adapter.stopped is True


def test_find_ble_controllers(mock_bable_no_ctrl):
    """Test if the function to get the controllers available works."""
    # Test with no controllers
    with pytest.raises(ExternalError):
        NativeBLEDeviceAdapter(port=None)

    # Test with one controller (valid)
    controller_valid = [Controller(1, '22:33:44:55:66:11', '#1', settings={'powered': True, 'low_energy': True})]
    mock_bable_no_ctrl.set_controllers(controller_valid)
    device_adapter = NativeBLEDeviceAdapter(port=None)
    assert device_adapter.controller_id == 1

    # Test with one controller (not valid)
    controller_not_valid = [Controller(0, '11:22:33:44:55:66', '#0')]
    mock_bable_no_ctrl.set_controllers(controller_not_valid)
    with pytest.raises(ExternalError):
        NativeBLEDeviceAdapter(port=None)

    # Test with multiple controllers
    controller_only_powered = [Controller(2, '33:44:55:66:11:22', '#2', settings={'powered': True})]
    mock_bable_no_ctrl.set_controllers(controller_valid + controller_not_valid + controller_only_powered)
    device_adapter = NativeBLEDeviceAdapter(port=None)
    assert device_adapter.controller_id == 1  # Because it is the only one who is both powered and low_energy

    # Test with given port (controller id) (valid)
    controller_valid2 = [Controller(3, '44:55:66:11:22:33', '#3', settings={'powered': True, 'low_energy': True})]
    mock_bable_no_ctrl.set_controllers(controller_valid + controller_not_valid + controller_valid2)
    device_adapter = NativeBLEDeviceAdapter(port=3)
    assert device_adapter.controller_id == 3

    # Test with given port (controller id) (not valid)
    with pytest.raises(ExternalError):
        NativeBLEDeviceAdapter(port=4)

    # Test with wrong format port (controller id): must be an int
    with pytest.raises(ValueError):
        NativeBLEDeviceAdapter(port='hci0')
        NativeBLEDeviceAdapter(port='hci0')


def test_scan(mock_bable):
    """Test to start and stop scans."""
    # Flag to know if `on_scan` callback has been called
    on_scan_called = [False]

    # Device information
    iotile_id = 0x7777
    pending_data = False
    low_voltage = False
    user_connected = False
    flags = pending_data | (low_voltage << 1) | (user_connected << 2) | (1 << 3) | (1 << 4)
    advertisement = {
        'controller_id': 1,
        'type': 0x00,
        'address': '12:23:34:45:56:67',
        'address_type': 'public',
        'rssi': -60,
        'uuid': TileBusService.uuid,
        'company_id': ArchManuID,
        'device_name': 'Test',
        'manufacturer_data': struct.pack("<LH", iotile_id, flags)
    }

    voltage = struct.pack("<H", int(3.8*256))
    reading = struct.pack("<HLLL", 0xFFFF, 0, 0, 0)
    scan_response = {
        'controller_id': 1,
        'type': 0x04,
        'address': '12:23:34:45:56:67',
        'address_type': 'public',
        'rssi': -60,
        'uuid': TileBusService.uuid,
        'company_id': ArchManuID,
        'device_name': 'Test',
        'manufacturer_data': voltage + reading
    }

    def on_scan(adapter_id, device_info, expiration_time):
        """Callback function called when a device has been scanned"""
        on_scan_called[0] = True

        assert device_info['uuid'] == iotile_id
        assert device_info['signal_strength'] == -60
        assert device_info['pending_data'] == pending_data
        assert device_info['low_voltage'] == low_voltage
        assert device_info['user_connected'] == user_connected
        assert device_info['connection_string'] == "{},{}" \
            .format(advertisement['address'], advertisement['address_type'])

    # Test to verify that scan is started when device_adapter is created
    device_adapter = NativeBLEDeviceAdapter(port=1, active_scan=True, on_scan=on_scan)
    assert device_adapter.scanning is True
    assert device_adapter._active_scan is True
    assert mock_bable.controllers_state[device_adapter.controller_id]['scanning']

    # Test with a complete IOTile device discovering (advertisement + scan response)
    mock_bable.simulate_device_found(device_adapter.controller_id, advertisement)
    assert on_scan_called[0] is False
    mock_bable.simulate_device_found(device_adapter.controller_id, scan_response)
    assert on_scan_called[0] is True

    # Try to start scan (already started): should not fail because we already were doing an active scan
    device_adapter.start_scan(active=True)
    assert device_adapter.scanning is True
    assert device_adapter._active_scan is True
    assert mock_bable.controllers_state[device_adapter.controller_id]['scanning']
    assert mock_bable.controllers_state[device_adapter.controller_id]['scanning']['active_scan'] is True

    # Test to stop scan
    device_adapter.stop_scan()
    assert device_adapter.scanning is False
    assert not mock_bable.controllers_state[device_adapter.controller_id]['scanning']

    # Test to stop scan (already stopped): should not fail
    device_adapter.stop_scan()
    assert device_adapter.scanning is False
    assert not mock_bable.controllers_state[device_adapter.controller_id]['scanning']

    # Start a new scan but in passive mode
    device_adapter.start_scan(active=False)
    assert device_adapter.scanning is True
    assert device_adapter._active_scan is False
    assert mock_bable.controllers_state[device_adapter.controller_id]['scanning']
    assert mock_bable.controllers_state[device_adapter.controller_id]['scanning']['active_scan'] is False

    # Receive an IOTile device advertisement. In passive mode, it should trigger the `on_scan` callback
    on_scan_called[0] = False
    mock_bable.simulate_device_found(device_adapter.controller_id, advertisement)
    assert on_scan_called[0] is True

    # Receive a non IOTile device advertisement. Should not trigger the `on_scan` callback
    on_scan_called[0] = False
    advertisement['uuid'] = SendHeaderChar
    mock_bable.simulate_device_found(device_adapter.controller_id, advertisement)
    assert on_scan_called[0] is False


def test_connect(mock_bable):
    """Test if connect and disconnect functions work."""
    # Device to connect information
    device_address = '11:11:11:11:11:11'
    device_address_type = 'random'

    device_adapter = NativeBLEDeviceAdapter(port=1)
    controller_state = mock_bable.controllers_state[device_adapter.controller_id]

    def on_connected(connection_id, adapter_id, success, failure_reason):
        """Callback function called when a device has been connected or connection failed."""
        assert success is True

    # Try to connect to the device (the device does not have any GATT table registered -> should fail)
    device_adapter.connect_async(0, '{},{}'.format(device_address, device_address_type), on_connected)
    assert mock_bable.counters['cancel_connection'] > 0  # Before connecting, we cancel all previous connections
    assert mock_bable.counters['connect'] > 0
    assert device_address in controller_state['connecting']  # Verify that the device is in "connecting" state

    time.sleep(0.1)  # Have to wait for connection manager to register the connection
    mock_bable.simulate_connected_event(device_adapter.controller_id, device_address)  # Simulate the connected event
    assert device_address not in controller_state['connecting']

    # On connect, device adapter should probe services and characteristics
    connection_handle = list(controller_state['connected'])[0]
    assert controller_state['connected'][connection_handle]['device'].address == device_address
    assert mock_bable.counters['probe_services'] > 0
    assert mock_bable.counters['probe_characteristics'] == 0
    assert mock_bable.counters['disconnect'] == 1  # Because we do not have the TileBusService in our GATT table

    # Simulate the disconnected event to end the disconnection
    time.sleep(0.1)
    mock_bable.simulate_disconnected_event(device_adapter.controller_id, connection_handle)

    # Register the proper GATT table in our mock
    services = [BLEService, TileBusService]
    characteristics = [
        NameChar,
        AppearanceChar,
        ReceiveHeaderChar,
        ReceivePayloadChar,
        SendHeaderChar,
        SendPayloadChar,
        StreamingChar,
        HighSpeedChar,
        TracingChar
    ]
    mock_bable.set_gatt_table(services, characteristics)

    # Retry to connect
    device_adapter.connect_async(0, '{},{}'.format(device_address, device_address_type), on_connected)
    assert device_address in controller_state['connecting']

    time.sleep(0.1)  # Have to wait for connection manager to register the connection
    mock_bable.simulate_connected_event(device_adapter.controller_id, device_address)
    assert device_address not in controller_state['connecting']

    connection_handle = list(controller_state['connected'])[0]
    assert controller_state['connected'][connection_handle]['device'].address == device_address
    assert mock_bable.counters['probe_services'] > 0
    assert mock_bable.counters['probe_characteristics'] > 0

    # It should not disconnect now
    assert mock_bable.counters['disconnect'] == 1  # Counter did not changed because now we have the TileBusService

    # Test if stopping with a connected device works
    device_adapter.stop_sync()
    assert mock_bable.counters['disconnect'] == 2  # Disconnection on stop


def test_connect_with_no_device(mock_bable):
    """Test to connect to a non-existing device."""
    device_address = '11:11:11:11:11:11'
    device_address_type = 'random'

    callback_called = threading.Event()

    def on_connected(connection_id, adapter_id, success, failure_reason):
        """Callback function called when a device has been connected or connection failed."""
        assert success is False
        callback_called.set()

    device_adapter = NativeBLEDeviceAdapter(port=1)
    device_adapter.set_config('default_timeout', 0.2)  # Set default timeout to not wait for 10 seconds

    # Try to connect
    device_adapter.connect_async(0, '{},{}'.format(device_address, device_address_type), on_connected)
    flag = callback_called.wait(timeout=device_adapter.get_config('default_timeout') + 1)
    assert flag is True  # Connection should have timed out after 0.2s and called the `on_connected` callback


def test_disconnect_not_connected_device(mock_bable):
    """Test to disconnect while not connected."""
    callback_called = threading.Event()

    def on_disconnected(connection_id, adapter_id, success, failure_reason):
        """Callback function called when the device has been disconnected or disconnection failed."""
        assert success is False
        callback_called.set()

    device_adapter = NativeBLEDeviceAdapter(port=1)
    device_adapter.set_config('default_timeout', 0.2)  # Set default timeout to not wait for 10 seconds

    # Try to disconnect
    device_adapter.disconnect_async(0, on_disconnected)
    flag = callback_called.wait(timeout=device_adapter.get_config('default_timeout') + 1)
    assert flag is True  # Disconnection should have timed out after 0.2s and called the `on_disconnected` callback


def test_rpc(connected_device_adapter):
    """Test to open RPC interface and send RPC."""
    device_adapter, mock_bable = connected_device_adapter

    # --- Opening RPC interface --- #
    packets_sent = {
        'header': False,
        'payload': False
    }
    callback_called = threading.Event()

    def on_write_request__open_rpc_interface(request, *params):
        """Callback function called when a write/write_without_response request has been sent to the mock_bable."""
        assert request['controller_id'] == 1
        assert request['attribute_handle'] in [ReceiveHeaderChar.config_handle, ReceivePayloadChar.config_handle]
        assert request['value'] == b'\x00\x01'

        if request['attribute_handle'] == ReceiveHeaderChar.config_handle:
            # Write request containing the header to open RPC interface
            assert packets_sent['header'] is False
            packets_sent['header'] = True
        else:
            # Write request containing the payload to open RPC interface
            assert packets_sent['payload'] is False
            packets_sent['payload'] = True

    def on_rpc_interface_opened(connection_id, adapter_id, success, *args):
        """Callback function called when the RPC interface has been opened."""
        assert success is True
        callback_called.set()

    # Register our on_write_request callback function in mock_bable
    mock_bable.on_write_request(on_write_request__open_rpc_interface)

    # Open the RPC interface
    device_adapter.open_interface_async(0, 'rpc', on_rpc_interface_opened)
    callback_called.wait(timeout=5.0)
    assert packets_sent['header'] is True
    assert packets_sent['payload'] is True

    # --- Sending RPC --- #
    packets_sent = {
        'header': False,
        'payload': False
    }
    callback_called.clear()

    def on_write_request__send_rpc(request, *params):
        """Callback function called when a write/write_without_response request has been sent to the mock_bable."""
        assert request['controller_id'] == 1
        assert request['attribute_handle'] in [SendHeaderChar.value_handle, SendPayloadChar.value_handle]

        if request['attribute_handle'] == SendHeaderChar.value_handle:
            # Write request containing the RPC header to send
            assert packets_sent['header'] is False
            packets_sent['header'] = True
        else:
            # Write request containing the RPC payload to send
            assert packets_sent['payload'] is False
            packets_sent['payload'] = True

    def on_rpc_response_received(connection_id, adapter_id, success, failure_reason, status, payload):
        """Callback function called when an RPC response has been received."""
        assert connection_id == 0
        assert success is True
        assert status == 0xFF
        assert payload == b''
        callback_called.set()

    # Register our new on_write_request callback function in mock_bable
    mock_bable.on_write_request(on_write_request__send_rpc)

    # Send the RPC request
    device_adapter.send_rpc_async(0, 120, 0xFFFF, bytearray([]), 1.0, on_rpc_response_received)

    # Simulate the RPC response
    mock_bable.notify(
        connection_handle=1,
        attribute_handle=ReceiveHeaderChar.value_handle,
        value=b'\xFF\x00\x00\x00',
    )
    flag = callback_called.wait(timeout=5.0)
    assert flag is True


def test_streaming(connected_device_adapter):
    """Test to open streaming interface and to receive reports."""
    device_adapter, mock_bable = connected_device_adapter

    # --- Opening streaming interface --- #
    callback_called = threading.Event()

    def on_write_request__open_streaming_interface(request, *params):
        """Callback function called when a write/write_without_response request has been sent to the mock_bable."""
        assert request['controller_id'] == 1
        assert request['attribute_handle'] == StreamingChar.config_handle
        assert request['value'] == b'\x00\x01'

    def on_streaming_interface_opened(connection_id, adapter_id, success, *args):
        """Callback function called when the streaming interface has been opened."""
        assert success is True
        callback_called.set()

    # Register our on_write_request callback function in mock_bable
    mock_bable.on_write_request(on_write_request__open_streaming_interface)

    # Open the streaming interface
    device_adapter.open_interface_async(0, 'streaming', on_streaming_interface_opened)
    flag = callback_called.wait(timeout=5.0)
    assert flag is True

    # --- Streaming reports --- #
    callback_called.clear()
    reports = []  # Will contain the reports received

    def on_write_request__stream_reports(request, *params):
        """Callback function called when a write/write_without_response request has been sent to the mock_bable."""
        assert request['controller_id'] == 1
        assert request['attribute_handle'] == StreamingChar.value_handle

    def on_report_callback(connection_id, report):
        """Callback function called when a report has been processed."""
        assert connection_id == 0
        reports.append(report)
        callback_called.set()

    # Register our report callback function to the `on_report` event
    device_adapter.add_callback('on_report', on_report_callback)

    # Register our new on_write_request callback function in mock_bable
    mock_bable.on_write_request(on_write_request__stream_reports)

    # Simulate a report sent by the device
    mock_bable.notify(
        connection_handle=1,
        attribute_handle=StreamingChar.value_handle,
        value=IndividualReadingReport.FromReadings(100, [IOTileReading(0, 1, 2)]).encode(),
    )
    flag = callback_called.wait(timeout=5.0)
    assert flag is True

    # We should have received exactly 1 report
    assert len(reports) == 1


def test_tracing(connected_device_adapter):
    """Test to open tracing interface and to receive traces."""
    device_adapter, mock_bable = connected_device_adapter

    # --- Opening tracing interface --- #
    callback_called = threading.Event()

    def on_write_request__open_tracing_interface(request, *params):
        """Callback function called when a write/write_without_response request has been sent to the mock_bable."""
        assert request['controller_id'] == 1
        assert request['attribute_handle'] == TracingChar.config_handle
        assert request['value'] == b'\x00\x01'

    def on_tracing_interface_opened(connection_id, adapter_id, success, *args):
        """Callback function called when the tracing interface has been opened."""
        assert success is True
        callback_called.set()

    # Register our on_write_request callback function in mock_bable
    mock_bable.on_write_request(on_write_request__open_tracing_interface)

    # Open the tracing interface
    device_adapter.open_interface_async(0, 'tracing', on_tracing_interface_opened)
    flag = callback_called.wait(timeout=5.0)
    assert flag is True

    # --- Receving traces --- #
    callback_called.clear()
    trace_chunks = []

    def on_write_request__receive_traces(request, *params):
        """Callback function called when a write/write_without_response request has been sent to the mock_bable."""
        assert request['controller_id'] == 1
        assert request['attribute_handle'] == TracingChar.value_handle

    def on_trace_received(connection_id, trace_chunk):
        """Callback function called when a chunk trace has been received."""
        assert connection_id == 0
        trace_chunks.append(trace_chunk)
        callback_called.set()

    # Register our trace received callback to the `on_trace` event
    device_adapter.add_callback('on_trace', on_trace_received)

    # Register our new on_write_request callback function in mock_bable
    mock_bable.on_write_request(on_write_request__receive_traces)

    # Simulate some traces
    trace_sent = b'\x00\x11\x22\x33\x44\x55\x66\x88\x99\x00\x11\x22\x33\x44\x55\x66\x88\x99'  # 20 bytes
    mock_bable.notify(
        connection_handle=1,
        attribute_handle=TracingChar.value_handle,
        value=trace_sent,
    )
    flag = callback_called.wait(timeout=5.0)
    assert flag is True

    assert len(trace_chunks) == 1  # We should have received only 1 chunk because we sent exactly 20 bytes
    assert trace_chunks[0] == trace_sent  # Verify that we received the trace sent


def test_send_script(connected_device_adapter):
    """Test to open script interface and to send a script."""
    device_adapter, mock_bable = connected_device_adapter

    # --- Opening script interface --- #
    callback_called = threading.Event()

    def on_write_request__open_script_interface(request, *params):
        """Callback function called when a write/write_without_response request has been sent to the mock_bable."""
        assert request['controller_id'] == 1
        assert request['attribute_handle'] == HighSpeedChar.config_handle
        assert request['value'] == b'\x00\x01'

    def on_script_interface_opened(connection_id, adapter_id, success, *args):
        """Callback function called when the script interface has been opened."""
        assert success is True
        callback_called.set()

    # Register our on_write_request callback function in mock_bable
    mock_bable.on_write_request(on_write_request__open_script_interface)

    # Open the script interface
    device_adapter.open_interface_async(0, 'script', on_script_interface_opened)
    flag = callback_called.wait(timeout=5.0)
    assert flag is True

    # --- Sending script --- #
    callback_called.clear()
    progress = {'done': 0, 'total': None}

    def on_write_request__send_script(request, *params):
        """Callback function called when a write/write_without_response request has been sent to the mock_bable."""
        assert request['controller_id'] == 1
        assert request['attribute_handle'] == HighSpeedChar.value_handle

    def on_progress_callback(done_count, total_count):
        """Callback function called when a script chunk has been sent to indicate progress."""
        if progress['total'] is not None:
            assert progress['total'] == total_count

        assert done_count >= progress['done']
        assert done_count <= total_count

        progress['total'] = total_count
        progress['done'] = done_count

    def on_script_sent(connection_id, adapter_id, success, failure_reason):
        """Callback function called when all the script has been sent."""
        assert success is True
        callback_called.set()

    # Register our new on_write_request callback function in mock_bable
    mock_bable.on_write_request(on_write_request__send_script)

    # Send the script
    script = bytes(b'ab')*100
    device_adapter.send_script_async(0, script, on_progress_callback, on_script_sent)
    flag = callback_called.wait(timeout=5.0)
    assert flag is True
    assert progress['done'] == progress['total'] - 1


def test_broadcast(mock_bable):
    """Test to broadcast a report in scan response."""
    # Create some reading
    broadcast_reading = IOTileReading(1, 0x1000, 100)

    # Device information
    iotile_id = 0x7777
    pending_data = False
    low_voltage = False
    user_connected = False
    flags = pending_data | (low_voltage << 1) | (user_connected << 2) | (1 << 3) | (1 << 4)
    advertisement = {
        'controller_id': 1,
        'type': 0x00,
        'address': '12:23:34:45:56:67',
        'address_type': 'public',
        'rssi': -60,
        'uuid': TileBusService.uuid,
        'company_id': ArchManuID,
        'device_name': 'Test',
        'manufacturer_data': struct.pack("<LH", iotile_id, flags)
    }

    voltage = struct.pack("<H", int(3.8*256))
    # Include the broadcast report in the scan response data
    reading = struct.pack("<HLLL", broadcast_reading.stream, broadcast_reading.value, broadcast_reading.raw_time, 0)
    scan_response = {
        'controller_id': 1,
        'type': 0x04,
        'address': '12:23:34:45:56:67',
        'address_type': 'public',
        'rssi': -60,
        'uuid': TileBusService.uuid,
        'company_id': ArchManuID,
        'device_name': 'Test',
        'manufacturer_data': voltage + reading
    }

    callback_called = threading.Event()
    reports = []

    def on_report_received(connection_id, report):
        """Callback function called when a report has been received."""
        assert connection_id is None
        assert isinstance(report, BroadcastReport)
        reports.append(report)
        callback_called.set()

    device_adapter = NativeBLEDeviceAdapter(port=1, active_scan=True)  # We should use active scan for now

    # Register our on_report_received callback
    device_adapter.add_callback('on_report', on_report_received)

    # Simulate a advertising report received
    mock_bable.simulate_device_found(device_adapter.controller_id, advertisement)

    # Simulate a scan response received
    mock_bable.simulate_device_found(device_adapter.controller_id, scan_response)
    flag = callback_called.wait(timeout=5.0)
    assert flag is True
    assert len(reports) == 1  # The scan response contains a broadcast report: it should have been processed

    # Verify that the report received is the same as the report broadcasted
    reading = reports[0].visible_readings[0]
    assert reading.stream == 0x1000
    assert reading.raw_time == 1
    assert reading.value == 100


def test_hardware_manager(mock_bable):
    """Test if the device adapter works correctly with the HardwareManager."""
    # Test using a wrong controller id
    with pytest.raises(ExternalError):
        hw = HardwareManager(port='ble:0')

    # Test without giving the controller id
    hw = HardwareManager(port='ble')
    hw.close()
