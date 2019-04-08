"""
Tests that an iotile rpcs return BusyResponse when the iotile is already
handling asynch rpc

Test includes a device with two tiles (see device.py):
* Tile 1 has an RPC Y that when called triggers it to send an RPC X to tile 2
    from a background task
* Tile 2 implements RPC X asynchronously and does not complete it until it
    gets a specific flag set
* Tile 1 and 2 also implement two other RPCs that are synchronous and
    let the proxy poll them to determine if they will return busy.
"""

import pytest
import os
from iotile.core.hw.exceptions import BusyRPCResponse
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.dev.registry import ComponentRegistry

path = os.path.join(os.path.dirname(__file__), 'busyresponse/device.py')

@pytest.fixture
def register_proxies():
    reg = ComponentRegistry()
    reg.clear()
    reg.clear_components()
    reg.register_extension('iotile.proxy', 'test_proxies', path)


@pytest.fixture
def hw():
    hw = HardwareManager(port='virtual:{}'.format(path))
    hw.connect_direct(1)

    yield hw

    hw.disconnect()
    hw.close()


def test_sync_request_during_async(register_proxies, hw):
    """
    1. Proxy calls RPC Y to start a long running background RPC
    2. Proxy then calls another synchronous RPC on tile 1 which succeeds
    3. Proxy then calls another synchronous RPC on tile 2 which should fail with busy
    4. Test case then sets flag on tile 2 to tell it to finish the async rpc
    5. Proxy then calls another synchronous RPC on tile 2 which should succeed
    """

    proxy1 = hw.get(11)
    assert proxy1.sync_rpc() == b'sync rpc tile01'

    proxy2 = hw.get(12)
    assert proxy2.sync_rpc() == b'sync rpc tile02'

    # Step 1
    proxy1.rpc_y()

    # Step 2
    assert proxy1.sync_rpc() == b'sync rpc tile01'

    # Step 3
    with pytest.raises(BusyRPCResponse):
        proxy2.sync_rpc()

    # Step 4
    proxy1.set_event()

    # Step 5
    assert proxy2.sync_rpc() == b'sync rpc tile02'
