"""Local fixtures for testing iotile-ext-cloud."""

import pytest
from iotile.core.dev.registry import ComponentRegistry
from iotile.cloud.cloud import IOTileCloud

from iotile.core.hw.hwmanager import HardwareManager

@pytest.fixture(scope="function")
def basic_cloud(mock_cloud_private_nossl):
    """A basic mock iotile.cloud initialized with default information.

    There is a single project with 5 devices that have ids 1-5 and
    a second inaccessible project with 1 device (id 6) in it.
    """

    ComponentRegistry.SetBackingStore('memory')

    domain, cloud = mock_cloud_private_nossl

    reg = ComponentRegistry()
    reg.set_config('cloud:server', domain)
    reg.set_config('arch:cloud_token', 'JWT_USER')
    reg.set_config('arch:cloud_token_type', 'jwt')

    cloud.quick_add_user('test@arch-iot.com', 'test')
    proj_id, _proj_slug = cloud.quick_add_project()
    proj2_id, _proj_slug = cloud.quick_add_project()

    devs = [cloud.quick_add_device(proj_id, x, streamers=[100, 200]) for x in range(1, 6)]
    client = IOTileCloud()

    cloud.quick_add_device(proj2_id)

    cloud.quick_add_sg(slug="water-meter-v1-1-0", app_tag=123)
    cloud.quick_add_sg(slug="water-meter-v1-1-1", app_tag=124)

    cloud.quick_add_dt(slug="internaltestingtemplate-v0-1-0", os_tag=234)
    cloud.quick_add_dt(slug="internaltestingtemplate-v0-1-1", os_tag=235)

    yield client, proj_id, cloud



@pytest.fixture(scope="function")
def ota_cloud(mock_cloud_private_nossl):
    """A basic mock iotile.cloud initialized with default information.

    There is a single project with 5 devices that have ids 1-5 and
    a second inaccessible project with 1 device (id 6) in it.

    Also adds ota deployments with various tags to check tagging logic
    """

    ComponentRegistry.SetBackingStore('memory')

    domain, cloud = mock_cloud_private_nossl

    reg = ComponentRegistry()
    reg.set_config('cloud:server', domain)
    reg.set_config('arch:cloud_token', 'JWT_USER')
    reg.set_config('arch:cloud_token_type', 'jwt')

    cloud.quick_add_user('test@arch-iot.com', 'test')
    proj_id, _proj_slug = cloud.quick_add_project()
    proj2_id, _proj_slug = cloud.quick_add_project()

    devs = [cloud.quick_add_device(proj_id, x, streamers=[100, 200]) for x in range(1, 7)]
    ota_devs = [cloud.quick_add_ota_device_info(x) for x in range(1, 7)]
    client = IOTileCloud()

    cloud.quick_add_device(proj2_id)

    cloud.quick_add_sg(slug="water-meter-v1-1-0", app_tag=123)
    cloud.quick_add_sg(slug="water-meter-v1-1-1", app_tag=124)

    cloud.quick_add_dt(slug="internaltestingtemplate-v0-1-0", os_tag=234)
    cloud.quick_add_dt(slug="internaltestingtemplate-v0-1-1", os_tag=235)

    # Need to create a fleet to start OTA
    cloud.quick_add_fleet(devices=[1,2], fleet_slug=1)
    cloud.quick_add_fleet(devices=[4,5], fleet_slug=2)
    cloud.quick_add_fleet(devices=[1,2,4,5,6], fleet_slug=3)
    cloud.quick_add_fleet(devices=[1,3,4,6], fleet_slug=4)

    # should always try to deploy from fleet 1 or 2 first, since they were added to the list first
    # even though release date is the same, order added takes precedence in this case

    criteria_eq = ['os_tag:eq:234', 'app_tag:eq:123', 'os_version:eq:0.0.2', 'app_version:eq:0.0.2']
    criteria_gt = ['os_tag:eq:233', 'app_tag:eq:122', 'os_version:gt:0.0.2', 'app_version:gteq:0.0.2']

    criteria_lt = ['os_tag:eq:235', 'app_tag:eq:124', 'os_version:lt:0.0.2', 'app_version:lteq:0.0.2']

    cloud.quick_add_deployment_to_fleet(fleet_id=1, deployment_id=1, criteria=criteria_eq)
    cloud.quick_add_deployment_to_fleet(fleet_id=2, deployment_id=2, criteria=criteria_gt)

    cloud.quick_add_deployment_to_fleet(fleet_id=3, deployment_id=3, criteria=criteria_lt)

    cloud.quick_add_deployment_to_fleet(fleet_id=4, deployment_id=4, criteria=criteria_lt, completed=True)

    yield client, proj_id, cloud

@pytest.fixture(scope="function")
def simple_hw():

    simple_file = """{{
        "device":
        {{
            "iotile_id": "{0}",
            "trace":
            [
                [0.001, "hello "],
                [0.001, "goodbye "]
            ],

            "simulate_time": true
        }}
    }}
"""

    for i in [1, 3, 4, 6]:
        fname = "dev" + str(i) + ".json"
        with open(fname, 'w') as tf:
            tf.write(simple_file.format(str(i)))

    with HardwareManager('virtual:reference_1_0@dev1.json;reference_1_0@dev4.json;reference_1_0@dev3.json;reference_1_0@dev6.json') as hw:
        yield hw
