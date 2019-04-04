"""Integration tests of the IOTileGateway class."""

import base64
import json
import pytest
from iotile.core.utilities import BackgroundEventLoop
from iotile.core.hw.reports import BroadcastReport
from iotile.core.hw import HardwareManager
from iotilegateway import IOTileGateway


@pytest.fixture(scope="function")
def loop():
    """A fresh background event loop."""

    loop = BackgroundEventLoop()

    loop.start()
    yield loop
    loop.stop()


@pytest.fixture(scope="function")
def running_gateway(loop):
    """A basic gateway with some virtual devices."""

    realtime_config = {
        "iotile_id": 10,
        "streams":
        {
            "0x5001": [0.001, 100],
            "0x100a": [0.001, 200]
        },

        "broadcast":
        {
            "0x1001": [0.020, 100],
            "0x2001": [0.020, 200]
        }
    }

    enc = base64.b64encode(json.dumps(realtime_config).encode('utf-8')).decode('utf-8')

    config = {
        'servers': [
            {
                "name": "websockets",
                "args":
                {
                    "port": None
                }
            }
        ],

        'adapters': [
            {
                "name": "virtual",
                "port": "realtime_test@#" + enc + ";simple"
            }
        ]
    }

    gateway = IOTileGateway(config, loop=loop)

    loop.run_coroutine(gateway.start())

    port = gateway.servers[0].port
    hw = HardwareManager(port="ws:127.0.0.1:%d/iotile/v1" % port)

    yield hw, gateway

    loop.run_coroutine(gateway.stop())


def test_broadcast(running_gateway):
    """Test that we can send broadcast readings through our ws connection."""

    hw, _gateway = running_gateway

    results = hw.scan()
    assert len(results) == 2
    assert sorted(x['uuid'] for x in results) == [1, 10]

    hw.enable_broadcasting()
    reports = hw.wait_broadcast_reports(2)

    assert len(reports) == 2


def test_streaming(running_gateway):
    """Test to make sure that we can stream through our ws connection.

    Also ensures that broadcast reports are not incorrectly mixed with
    streaming reports.
    """

    hw, _gateway = running_gateway

    hw.connect(10)

    try:
        hw.enable_streaming()
        reports = hw.wait_reports(10)
    finally:
        hw.disconnect()

    assert len(reports) == 10
    for report in reports:
        assert not isinstance(report, BroadcastReport)


def test_rpc(running_gateway):
    """Test to make sure we can call an RPC through our ws connection."""

    hw, _gateway = running_gateway

    hw.connect(1)
    hw.controller()
