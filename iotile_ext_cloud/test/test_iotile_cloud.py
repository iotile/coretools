"""Test IOTileCloud object using a mock cloud."""

import pytest
import requests_mock
from iotile.core.exceptions import ArgumentError
from iotile.core.dev.config import ConfigManager
from iotile.cloud.config import link_cloud


import datetime
from dateutil.tz import tzutc
from iotile.cloud.cloud import IOTileCloud
from iotile.core.dev.registry import ComponentRegistry
from iotile.core.exceptions import ArgumentError, ExternalError

def test_basic_cloud(basic_cloud):
    """Make sure we can set up the mock cloud and create an IOTileCloud."""

    cloud, _proj_id, _server = basic_cloud
    assert cloud.refresh_required


def test_device_info(basic_cloud):
    """Make sure we can get device info."""

    cloud, proj_id, _server = basic_cloud

    data = cloud.device_info(1)
    assert data['id'] == 1
    assert data['project'] == proj_id
    with pytest.raises(ArgumentError):
        cloud.device_info(10)

def test_device_list(basic_cloud):
    """Make sure the device_list api works."""

    cloud, proj_id, _server = basic_cloud

    devs = cloud.device_list()
    devs_proj = cloud.device_list(project_id=proj_id)

    assert set(devs) == set([1, 2, 3, 4, 5, 6])
    assert set(devs_proj) == set([1, 2, 3, 4, 5])


def test_highest_acknowledged(basic_cloud):
    """Make sure we can get the highest_acknowledged_values."""

    cloud, proj_id, _server = basic_cloud

    assert cloud.highest_acknowledged(1, 0) == 100
    assert cloud.highest_acknowledged(1, 1) == 200

    with pytest.raises(ArgumentError):
        cloud.highest_acknowledged(6, 0)

def test_set_sensorgraph_basic(basic_cloud):
    """Make sure we can properly change sensorgraph"""
    
    cloud, proj_id, _server = basic_cloud
    data = cloud.device_info(1)
    assert data['sg'] == 'water-meter-v1-1-0'

    cloud.set_sensorgraph(1, 'water-meter-v1-1-1')
    data = cloud.device_info(1)
    assert data['sg'] == 'water-meter-v1-1-1'

def test_set_sensorgraph_check(basic_cloud):
    """Make sure we can properly change sensorgraph with app_tag checking""" 
    cloud, proj_id, _server = basic_cloud
    data = cloud.device_info(1)
    assert data['sg'] == 'water-meter-v1-1-0'

    #Try changing sensorgraph while checking app_tag
    cloud.set_sensorgraph(1, 'water-meter-v1-1-1', app_tag=124)
    data = cloud.device_info(1)
    assert data['sg'] == 'water-meter-v1-1-1'

    #Try chaging sensorgraph with incorrect app_tag
    with pytest.raises(ArgumentError):
        cloud.set_sensorgraph(1, 'water-meter-v1-1-0', app_tag=0)
    data = cloud.device_info(1)
    assert data['sg'] == 'water-meter-v1-1-1'

    #Trying changing to a non-existant sg
    with pytest.raises(ExternalError):
        cloud.set_sensorgraph(1, 'water-meter-v1-1-2')
    data = cloud.device_info(1)
    assert data['sg'] == 'water-meter-v1-1-1'

def test_set_device_template_basic(basic_cloud):
    """Make sure we can properly change device template""" 
    cloud, proj_id, _server = basic_cloud
    data = cloud.device_info(1)
    assert data['template'] == 'internaltestingtemplate-v0-1-0'

    cloud.set_device_template(1, 'internaltestingtemplate-v0-1-1')
    data = cloud.device_info(1)
    assert data['template'] == 'internaltestingtemplate-v0-1-1'

def test_set_device_template_check(basic_cloud):
    """Make sure we can properly change device template with os tag checking""" 
    cloud, proj_id, _server = basic_cloud
    data = cloud.device_info(1)
    assert data['template'] == 'internaltestingtemplate-v0-1-0'

    #Try changing device_template while checking os_tag
    cloud.set_device_template(1, 'internaltestingtemplate-v0-1-1', os_tag=235)
    data = cloud.device_info(1)
    assert data['template'] == 'internaltestingtemplate-v0-1-1'

    #Try chaging device template with incorrect os_tag
    with pytest.raises(ArgumentError):
        cloud.set_device_template(1, 'internaltestingtemplate-v0-1-0', os_tag=0)
    data = cloud.device_info(1)
    assert data['template'] == 'internaltestingtemplate-v0-1-1'

    #Trying changing to a non-existant template
    with pytest.raises(ExternalError):
        cloud.set_device_template(1, 'internaltestingtemplate-v0-1-2')  
    data = cloud.device_info(1)
    assert data['template'] == 'internaltestingtemplate-v0-1-1'