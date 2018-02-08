"""Test IOTileCloud object using a mock cloud."""

import pytest
from iotile.core.exceptions import ArgumentError


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

def test_set_sensorgraph(basic_cloud):
    """Make sure we can properly change sensorgraph"""
    cloud, proj_id, _server = basic_cloud
    data = cloud.device_info(1)
    assert data['sg'] == "water-meter-v1-1-0"
    cloud.set_sensorgraph(1, "water-meter-v1-1-1")
    assert data['sg'] == "water-meter-v1-1-1"

def test_set_device_template(basic_cloud):
    """Make sure we can properly change device template"""
    cloud, proj_id, _server = basic_cloud
    data = cloud.device_info(1)
    assert data['template'] == "internaltestingtemplate-v0-1-0"
    cloud.set_device_template(1, "internaltestingtemplate-v0-1-1", 0)
    assert data['template'] == "internaltestingtemplate-v0-1-1"

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

