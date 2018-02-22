"""Tests to ensure that IOTileApp matching works correctly."""

import os
import pytest
from iotile.core.hw import HardwareManager, IOTileApp
from iotile.core.dev.semver import SemanticVersionRange
from iotile.core.exceptions import HardwareError


class FakeApp(IOTileApp):
    """A basic fake app for testing."""

    @classmethod
    def MatchInfo(cls):
        return [(2100, SemanticVersionRange.FromString("^2.3.0"), 50)]

    @classmethod
    def AppName(cls):
        return 'fakeapp'

@pytest.fixture(scope="function")
def virtual_app():
    path = os.path.join(os.path.dirname(__file__), 'virtual_app_device.py')
    hw = HardwareManager(port="virtual:%s" % path)

    hw.connect(1)
    yield hw
    hw.disconnect()


@pytest.fixture(scope="function")
def register_apps():
    HardwareManager.ClearDevelopmentApps()
    HardwareManager.RegisterDevelopmentApp(FakeApp)

    yield
    HardwareManager.ClearDevelopmentApps()


def test_noapp_matching(virtual_app):
    """Make sure we throw an exception when no matching app is found."""

    hw = virtual_app

    with pytest.raises(HardwareError):
        hw.app()

    # Make sure we can still force a match
    info = hw.app('device_info')


def test_app_matching(virtual_app, register_apps):
    """Make sure matching by name and version works."""

    hw = virtual_app

    fake = hw.app()
    assert isinstance(fake, FakeApp)

    # Make sure we can still force a match
    info = hw.app('device_info')
