"""Test coverage of the cloud_uploader iotile app."""

import os
import pytest
from iotile.core.hw import HardwareManager

@pytest.fixture(scope='function')
def uploader_app():
    """A reference device with a streamer and loaded with data."""

    with HardwareManager(port="emulated:reference_1_0") as hw:
        con = hw.get(8, uuid=1, force='NRF52 ')
        sg = con.sensor_graph()

        sg.add_streamer('output 1', 'controller', False, 'hashedlist', 'telegram')
        sg.push_many('output 1', 10, 100)

        app = hw.app(name='cloud_uploader')

        yield app


def test_basic(uploader_app):
    """Make sure we can basically download reports."""

    reports = uploader_app.download(0, acknowledge=False)
    assert len(reports) == 1


def test_save(uploader_app, tmpdir):
    """Make sure we can save report files locally."""

    save_path = str(tmpdir.join('reports'))

    assert not os.path.isdir(save_path)

    uploader_app.save_locally(save_path, trigger=0)

    assert os.path.isdir(save_path)
    assert len(os.listdir(save_path)) == 1

    print(os.listdir(save_path)[0])
