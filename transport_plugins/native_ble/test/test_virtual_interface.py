"""
Unit tests for native BLE transport plugin - tests of the NativeBLEVirtualInterface.
"""

import json
import pytest
import threading
import time
from iotile_transport_native_ble.tilebus import *
from iotile.core.hw.reports import IOTileReportParser
from test.devices_factory import build_report_device, build_tracing_device, get_report_device_string, \
    get_tracing_device_string

pytestmark = pytest.mark.skip


@pytest.fixture(scope="function")
def virtual_interface(mock_bable, request):
    """Initialize the NativeBLEVirtualInterface with a given device."""
    port = request.param['port']
    config = {
        'port': port
    }

    device = request.param['device']

    interface = NativeBLEVirtualInterface(config)
    interface.start(device)

    # Call the process function periodically (in a separated thread)
    def _call_process():
        while True:
            interface.process()
            time.sleep(0.1)

    process_thread = threading.Thread(target=_call_process, name='VirtualInterfaceProcessThread')
    process_thread.daemon = True
    process_thread.start()

    return mock_bable, interface


@pytest.fixture(scope="function")
def connected_virtual_interface(virtual_interface):
    """Create an already connected NativeBLEVirtualInterface."""
    mock_bable, interface = virtual_interface
    device_address = '11:11:11:11:11:11'

    mock_bable.simulate_connected_event(interface.controller_id, device_address)
    assert interface.connected is True

    return mock_bable, interface



@pytest.mark.parametrize('virtual_interface', [{'device': build_report_device(), 'port': None}], indirect=True)
def test_start_stop(virtual_interface):
    """Test to start and stop the virtual interface."""
    mock_bable, interface = virtual_interface
    # Check we are using the right controller ID
    assert interface.controller_id == 1
    # Check we are not connected
    assert interface.connected is False

    controller_state = mock_bable.controllers_state[interface.controller_id]

    # Verify that it registered the GATT table
    assert mock_bable.counters['set_gatt_table'] == 1
    assert len(controller_state['gatt_table']['services']) == 2
    assert len(controller_state['gatt_table']['characteristics']) == 9

    # Verify that it started to advertise correctly
    assert mock_bable.counters['set_advertising'] == 2  # 1 to disable advertising, 1 to start it
    assert controller_state['advertising']['company_id'] == ArchManuID

    # Test to stop the interface
    interface.stop()
    # Check that it stopped to advertise
    assert mock_bable.counters['set_advertising'] == 3
    assert not controller_state['advertising']


@pytest.mark.parametrize('virtual_interface', [{'device': build_report_device(), 'port': 1}], indirect=True)
def test_connect_disconnect(virtual_interface):
    """Test the connection and disconnection."""
    mock_bable, interface = virtual_interface
    device_address = '11:11:11:11:11:11'

    # Simulate a connected event on the wrong controller id
    mock_bable.simulate_connected_event(0, device_address)
    assert interface.connected is False

    # Simulate a connected event on the right controller id
    mock_bable.simulate_connected_event(interface.controller_id, device_address)
    assert interface.connected is True

    num_set_advertising = mock_bable.counters['set_advertising']

    # Simulate a disconnected event
    mock_bable.simulate_disconnected_event(interface.controller_id, interface._connection_handle)
    assert interface.connected is False

    time.sleep(0.1)
    # Verify that it restarted advertising after disconnection (because connection automatically stops advertising)
    assert mock_bable.counters['set_advertising'] == num_set_advertising + 1
    assert mock_bable.controllers_state[interface.controller_id]['advertising']


@pytest.mark.parametrize('virtual_interface', [{'device': build_report_device(), 'port': 1}], indirect=True)
def test_stop_while_connected(connected_virtual_interface):
    """Test to stop the virtual interface while connected."""
    mock_bable, interface = connected_virtual_interface
    assert mock_bable.counters['disconnect'] == 0

    interface.stop()
    assert mock_bable.counters['disconnect'] == 1
    assert mock_bable.started is False


@pytest.mark.parametrize('virtual_interface', [{'device': build_report_device(), 'port': 1}], indirect=True)
def test_rpc(connected_virtual_interface):
    """Test to receive an RPC request and send back the response."""
    mock_bable, interface = connected_virtual_interface
    connection_handle = interface._connection_handle

    # --- Opening RPC interface --- #
    assert interface.header_notif is False
    assert interface.payload_notif is False

    # Simulate a write on the RPC header characteristic to open the interface
    mock_bable.write_without_response(connection_handle, ReceiveHeaderChar.config_handle, b'\x01\x00')
    assert interface.header_notif is True
    assert interface.payload_notif is False

    # Simulate a write on the RPC payload characteristic to open the interface
    mock_bable.write_without_response(connection_handle, ReceivePayloadChar.config_handle, b'\x01\x00')
    assert interface.header_notif is True
    assert interface.payload_notif is True

    # --- Handling RPC --- #
    response_received = threading.Event()

    def on_notification_received(success, result, failure_reason):
        """Callback function called when a notification has been received (the virtual interface sends a notification
        as the RPC response)."""
        assert success is True
        assert result['controller_id'] == interface.controller_id
        assert result['connection_handle'] == connection_handle
        assert result['attribute_handle'] == ReceiveHeaderChar.value_handle
        assert result['value'] == b'\xff\x00\x00\x00'
        response_received.set()

    # Register our notification received callback into the mock_bable.
    controller_state = mock_bable.controllers_state[interface.controller_id]
    controller_state['connected'][connection_handle]['on_notification_received'] = (on_notification_received, [])

    # Prepare and send an RPC request
    address = 120
    rpc_id = 0xFFFF
    header = bytearray([0, 0, rpc_id & 0xFF, (rpc_id >> 8) & 0xFF, address])
    mock_bable.write_without_response(connection_handle, SendHeaderChar.value_handle, header)
    flag = response_received.wait(timeout=5.0)
    assert flag is True


@pytest.mark.parametrize('virtual_interface', [{'device': build_report_device(), 'port': 1}], indirect=True)
def test_stream(connected_virtual_interface):
    """Test to stream reports after streaming interface has been opened."""
    # Get the device configuration from the configuration file.
    with open(get_report_device_string().split('@')[-1], "r") as conf_file:
        config = json.load(conf_file)
        num_reports = int(config['device']['num_readings']) / int(config['device']['report_length'])

    mock_bable, interface = connected_virtual_interface
    connection_handle = interface._connection_handle

    reports_received = threading.Event()
    reports = []

    def on_report(report, connection_id):
        """Callback function called when a report has been processed."""
        reports.append(report)
        if len(reports) == num_reports:  # If all the reports have been received, we are done
            reports_received.set()

    # Create a report parser and register our on_report callback
    parser = IOTileReportParser(report_callback=on_report)

    def on_notification_received(success, result, failure_reason):
        """Callback function called when a notification has been received (the virtual interface sends a notification
        to stream reports)"""
        assert success is True
        assert result['controller_id'] == interface.controller_id
        assert result['connection_handle'] == connection_handle
        assert result['attribute_handle'] == StreamingChar.value_handle

        parser.add_data(result['value'])  # Add the received report chunk to the report parser

    # Register our notification received callback into the mock_bable.
    controller_state = mock_bable.controllers_state[interface.controller_id]
    controller_state['connected'][connection_handle]['on_notification_received'] = (on_notification_received, [])

    # Open the streaming interface
    assert interface.streaming is False
    mock_bable.write_without_response(connection_handle, StreamingChar.config_handle, b'\x01\x00')
    assert interface.streaming is True

    flag = reports_received.wait(timeout=5.0)
    assert flag is True


@pytest.mark.parametrize('virtual_interface', [{'device': build_tracing_device(), 'port': 1}], indirect=True)
def test_tracing(connected_virtual_interface):
    """Test to send traces after the tracing interface has been opened."""
    # Get the device configuration from the configuration file.
    with open(get_tracing_device_string().split('@')[-1], "r") as conf_file:
        config = json.load(conf_file)
        traces_sent = config['device']['ascii_data']

    mock_bable, interface = connected_virtual_interface
    connection_handle = interface._connection_handle

    all_received = threading.Event()
    traces_received = [bytearray()]

    def on_notification_received(success, result, failure_reason):
        """Callback function called when a notification has been received (the virtual interface sends a notification
        to send traces)"""
        assert success is True
        assert result['controller_id'] == interface.controller_id
        assert result['connection_handle'] == connection_handle
        assert result['attribute_handle'] == TracingChar.value_handle

        traces_received[0] += result['value']  # Collect the traces
        if len(traces_received[0]) == len(traces_sent):  # If we have received all the traces, we are done
            all_received.set()

    # Register our notification received callback into the mock_bable.
    controller_state = mock_bable.controllers_state[interface.controller_id]
    controller_state['connected'][connection_handle]['on_notification_received'] = (on_notification_received, [])

    # Open the tracing interface
    assert interface.tracing is False
    mock_bable.write_without_response(connection_handle, TracingChar.config_handle, b'\x01\x00')
    assert interface.tracing is True

    flag = all_received.wait(timeout=5.0)
    assert flag is True
    assert traces_received[0].decode() == traces_sent  # Verify that we received the right traces
