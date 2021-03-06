# Pytest configuration file: will be run before tests to define fixtures
import os
import pytest
import sys
import threading
import time

skip_imports = False
if sys.platform not in ['linux', 'linux2']:
    collect_ignore = [f for f in os.listdir(os.path.dirname(__file__)) if f.startswith('test_')]
    skip_imports = True

if not skip_imports:
    from iotile_transport_native_ble.device_adapter import NativeBLEDeviceAdapter
    from iotile_transport_native_ble.tilebus import *


@pytest.fixture(scope='function')
def connected_device_adapter(mock_bable):
    """Create an already connected NativeBLEDeviceAdapter, using the mocked BaBLEInterface."""
    device_address = '11:11:11:11:11:11'
    device_address_type = 'random'

    callback_called = threading.Event()

    def on_connected(connection_id, adapter_id, success, failure_reason):
        """Callback function called when a connection has been completed (succeeded or failed)."""
        assert success is True
        callback_called.set()

    device_adapter = NativeBLEDeviceAdapter(port=1)
    device_adapter.set_config('default_timeout', 0.2)

    # Register the GATT table
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

    device_adapter.connect_async(0, '{},{}'.format(device_address, device_address_type), on_connected)

    time.sleep(0.1)  # Wait for the connection manager to process the connection

    mock_bable.simulate_connected_event(device_adapter.controller_id, device_address)
    callback_called.wait(timeout=10)

    return device_adapter, mock_bable
