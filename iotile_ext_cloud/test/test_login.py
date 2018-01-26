import pytest
import requests_mock
import datetime
from dateutil.tz import tzutc
from iotile.cloud.cloud import IOTileCloud
from iotile.cloud.config import link_cloud
from iotile.core.dev.config import ConfigManager
from iotile.core.dev.registry import ComponentRegistry
from iotile.core.exceptions import ArgumentError, ExternalError
import json

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


def test_check_time():
    """ Make sure we can check if the time is correct"""

    json_true = {'now': datetime.datetime.now(tzutc()).strftime('%a, %d %b %Y %X %Z')}
    json_false = {'now': 'Wed, 01 Sep 2010 17:30:32 GMT'}
    payload = {
        'jwt': 'big-token',
        'username': 'user1'
    }

    manager = ConfigManager()

    with requests_mock.Mocker() as mocker:

        mocker.post('https://iotile.cloud/api/v1/auth/login/', json=payload)
        link_cloud(manager, 'user1@random.com', 'password')
        cloud = IOTileCloud()
        mocker.get('https://iotile.cloud/api/v1/server/', json=json_true)
        assert cloud.check_time() == True
        mocker.get('https://iotile.cloud/api/v1/server/', json=json_false)
        assert cloud.check_time() == False


def test_get_fleet():
    """Make sure we can get fleets."""

    auth_payload = {
        'jwt': 'big-token',
        'username': 'user1'
    }
    test_payload = {"count":1,
              "next":"Null",
              "previous":"Null",
              "results":[{"device":"d--0000-0000-0000-0001","always_on":True,"is_access_point":False}]}

    expected = {
        "d--0000-0000-0000-0001":{
            "always_on":True,
            "is_access_point":False}
    }
    manager = ConfigManager()
    with requests_mock.Mocker() as mocker:

        mocker.post('https://iotile.cloud/api/v1/auth/login/', json=auth_payload)
        link_cloud(manager, 'user1@random.com', 'password')
        cloud = IOTileCloud()
        mocker.get('https://iotile.cloud/api/v1/fleet/g--0000-0000-0001/devices/', json=test_payload)
        mocker.get('https://iotile.cloud/api/v1/fleet/g--0000-0000-0002/devices/', status_code=404)
        assert cloud.get_fleet(1) == expected
        with pytest.raises(ArgumentError):
            cloud.get_fleet(2)
        with pytest.raises(ArgumentError):
            cloud.get_fleet(pow(16,12) + 1)


def test_get_whitelist():
    """ Make sure we can retrieve the whitelist correctly """
    with open('test/large_mock_answer.json') as lma:
        j = json.load(lma)
        test_payload = j['whitelist_test']
        p1 = j['whitelist_g1']
        p2 = j['whitelist_g2']
        p3 = j['whitelist_g3']
        expected = j['expected']
        empty_whitelist_test = j['empty_whitelist_test']
        p4 = j['whitelist_g4']
    payload = {
        'jwt': 'big-token',
        'username': 'user1'
    }

    manager = ConfigManager()
    with requests_mock.Mocker() as mocker:

        mocker.post('https://iotile.cloud/api/v1/auth/login/', json=payload)
        link_cloud(manager, 'user1@random.com', 'password')
        cloud = IOTileCloud()
        mocker.get('https://iotile.cloud/api/v1/fleet/?device=d--0000-0000-0000-0001', status_code=404)
        with pytest.raises(ExternalError):
            cloud.get_whitelist(1)
        mocker.get('https://iotile.cloud/api/v1/fleet/?device=d--0000-0000-0000-0002', json={'results':[]})
        with pytest.raises(ExternalError):
            cloud.get_whitelist(2)
        mocker.get('https://iotile.cloud/api/v1/fleet/?device=d--0000-0000-0000-01bd', json=test_payload)
        mocker.get('https://iotile.cloud/api/v1/fleet/g--0000-0000-0001/devices/', json=p1)
        mocker.get('https://iotile.cloud/api/v1/fleet/g--0000-0000-0002/devices/', json=p2)
        mocker.get('https://iotile.cloud/api/v1/fleet/g--0000-0000-0003/devices/', json=p3)
        assert cloud.get_whitelist(0x1bd) == expected
        mocker.get('https://iotile.cloud/api/v1/fleet/?device=d--0000-0000-0000-01bd', json=empty_whitelist_test)
        mocker.get('https://iotile.cloud/api/v1/fleet/g--0000-0000-0004/devices/', json=p4)
        with pytest.raises(ExternalError):
            cloud.get_whitelist(0x1bd)

