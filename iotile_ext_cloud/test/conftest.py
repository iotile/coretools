"""Local fixtures for testing iotile-ext-cloud."""

import pytest
from iotile.core.dev.registry import ComponentRegistry
from iotile.cloud.cloud import IOTileCloud


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
