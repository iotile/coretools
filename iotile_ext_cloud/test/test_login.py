import pytest
import requests_mock
from iotile.cloud.cloud import IOTileCloud
from iotile.cloud.config import link_cloud
from iotile.core.dev.config import ConfigManager
from iotile.core.dev.registry import ComponentRegistry


@pytest.fixture
def registry():
    reg = ComponentRegistry()
    reg.clear()

    yield reg

    reg.clear()


def test_login(registry):
    """Make sure successful login is properly handled."""

    payload = {
        'jwt': 'big-token',
        'username': 'user1'
    }

    manager = ConfigManager()

    with requests_mock.Mocker() as mocker:
        mocker.post('https://iotile.cloud/api/v1/auth/login/', json=payload)

        link_cloud(manager, 'user1@random.com', 'password')

    assert registry.get_config('arch:cloud_user') == 'user1'
    assert registry.get_config('arch:cloud_token') == 'big-token'


def test_refresh(registry):
    """Make sure we can properly refresh our jwt token."""

    payload = {
        'token': 'new-token'
    }

    registry.set_config("arch:cloud_token", 'old-token')
    registry.set_config("arch:cloud_user", 'test_user')

    cloud = IOTileCloud()

    with requests_mock.Mocker() as mocker:
        mocker.post('https://iotile.cloud/api/v1/auth/api-jwt-refresh/', json=payload)

        cloud.refresh_token()

    assert registry.get_config('arch:cloud_token') == 'new-token'


def test_alternative_domains(registry):
    """Make sure we can specify an alternative domain."""

    payload = {
        'jwt': 'big-token',
        'username': 'user1'
    }

    manager = ConfigManager()
    manager.set('cloud:server', 'https://testcloud.com')

    with requests_mock.Mocker() as mocker:
        mocker.post('https://testcloud.com/api/v1/auth/login/', json=payload)

        link_cloud(manager, 'user1@random.com', 'password')

    assert registry.get_config('arch:cloud_user') == 'user1'
    assert registry.get_config('arch:cloud_token') == 'big-token'

    cloud = IOTileCloud()

    payload = {
        'token': 'new-token'
    }

    with requests_mock.Mocker() as mocker:
        mocker.post('https://testcloud.com/api/v1/auth/api-jwt-refresh/', json=payload)

        cloud.refresh_token()

    assert registry.get_config('arch:cloud_token') == 'new-token'
