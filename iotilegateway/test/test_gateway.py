"""Integration tests of the IOTileGateway class."""

import pytest
import base64
import json
from iotile.core.hw.reports import BroadcastReport
from iotilegateway import IOTileGateway
from iotile.core.hw import HardwareManager


@pytest.fixture(scope="function")
def running_gateway():
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

    enc = base64.b64encode(json.dumps(realtime_config))

    config = {
        'agents': [
            {
                "name": "websockets",
                "args":
                {
                    "port": "unused"
                }
            }
        ],

        'adapters': [
            {
                "name": "virtual",
                "port": "realtime_test@#" + enc
            }
        ]
    }

    gateway = IOTileGateway(config)

    gateway.start()
    gateway.loaded.wait(2.0)

    hw = HardwareManager(port="ws:127.0.0.1:%d/iotile/v1" % gateway.agents[0].port)

    yield hw, gateway

    gateway.stop()


def test_broadcast(running_gateway):
    """Test that we can send broadcast readings through our ws connection."""

    hw, _gateway = running_gateway

    results = hw.scan()
    assert len(results) == 1
    assert results[0]['uuid'] == 10

    hw.enable_broadcasting()
    reports = hw.wait_broadcast_reports(2)

    assert len(reports) == 2


def test_streaming(running_gateway):
    """Test to make sure that we can stream through our ws connection.

    Also ensures that broadcast reports are not incorrectly mixed with
    streaming reports.
    """

    hw, _gateway = running_gateway

    results = hw.scan()
    assert len(results) == 1
    assert results[0]['uuid'] == 10

    hw.connect(10)

    try:
        hw.enable_streaming()
        reports = hw.wait_reports(10)
    finally:
        hw.disconnect()

    assert len(reports) == 10
    for report in reports:
        assert not isinstance(report, BroadcastReport)
