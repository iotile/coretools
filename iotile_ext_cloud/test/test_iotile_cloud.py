"""Test IOTileCloud object using a mock cloud."""

import pytest
import datetime
from builtins import range
from dateutil.tz import tzutc

from iotile.core.exceptions import ArgumentError
from iotile.core.dev.config import ConfigManager
from iotile.cloud.config import link_cloud
from iotile.core.hw.reports import IndividualReadingReport, SignedListReport, FlexibleDictionaryReport, IOTileReading
from iotile.cloud.cloud import IOTileCloud
from iotile.cloud.cloud import Acknowledgement
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


def test_device_acknowledgements(basic_cloud):
    """Make sure we can get device acknowledgements"""

    cloud, proj_id, _server = basic_cloud

    acknowledgements = cloud.device_acknowledgements(1)

    assert len(acknowledgements) == 2

    acknowledgements.sort(key=lambda x: x.index)

    assert acknowledgements[0].ack == 100
    assert acknowledgements[1].ack == 200


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


def make_sequential(iotile_id, stream, num_readings, give_ids=False, fmt="signed_list"):
    readings = []

    for i in range(0, num_readings):
        if give_ids:
            reading = IOTileReading(i, stream, i, reading_id=i+1)
        else:
            reading = IOTileReading(i, stream, i)

        readings.append(reading)

    if fmt == "signed_list":
        return SignedListReport.FromReadings(iotile_id, readings)

    return FlexibleDictionaryReport.FromReadings(iotile_id, readings, [])


def test_report_upload(basic_cloud):
    """Make sure we can properly upload reports to the cloud."""

    cloud, proj_id, server = basic_cloud

    ind_report = IndividualReadingReport.FromReadings(10, [IOTileReading(3, 1, 2)])
    signed_report = make_sequential(1, 0x5000, 10, give_ids=True)
    dict_report = make_sequential(1, 0x5000, 10, give_ids=True, fmt="flexible_dict")

    with pytest.raises(ArgumentError):
        cloud.upload_report(ind_report)

    cloud.upload_report(signed_report)
    cloud.upload_report(dict_report)
