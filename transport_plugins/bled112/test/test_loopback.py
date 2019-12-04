"""If there are two bled112 dongles on this computer attempt to setup a loopback test

We will serve a virtual device over one bled112 and connect to it with the other bled112
"""

import pytest
import subprocess
from iotile_transport_bled112.bled112 import BLED112Adapter
from iotile.core.hw.hwmanager import HardwareManager
import time
import signal

pytestmark = pytest.mark.hardware('loopback')

@pytest.fixture(scope="module")
def loopback_devices():
    vdev = subprocess.Popen(['virtual_device', 'bled112', 'report_test'])

    try:
        hw = HardwareManager(port='bled112')

        yield hw

        hw.close()
    finally:
        vdev.terminate()


def test_loopback(loopback_devices):
    """Ensure that we can connect to a device, send it rpcs and get reports."""

    hw = loopback_devices

    hw.scan()
    hw.connect(1)
    con = hw.controller()
    assert con.ModuleName() == 'Rptdev'

    hw.enable_streaming()
    _reports = hw.wait_reports(11, timeout=5.0)
