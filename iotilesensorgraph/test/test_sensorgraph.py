"""Test to make sure we can create and use SensorGraph objects."""

from iotile.sg import SensorGraph, DeviceModel, SensorLog, DataStream, SlotIdentifier
from iotile.sg.known_constants import config_user_tick_secs
from iotile.core.hw.reports import IOTileReading


def test_basic_sensorgraph():
    """Make sure we can parse, load and run a basic sensor graph."""

    model = DeviceModel()
    log = SensorLog(model=model)
    sg = SensorGraph(log, model=model)

    sg.add_node('(input 1 always && input 2 when count >= 1) => unbuffered 1 using copy_all_a')
    sg.process_input(DataStream.FromString('input 1'), IOTileReading(0, 1, 1), rpc_executor=None)
    assert sg.sensor_log.inspect_last(DataStream.FromString('unbuffered 1')).value == 1


def test_usertick():
    """Make sure we properly can set the user tick input."""

    model = DeviceModel()
    log = SensorLog(model=model)
    sg = SensorGraph(log, model=model)

    assert sg.user_tick() == 0

    sg.add_config(SlotIdentifier.FromString('controller'), config_user_tick_secs, 'uint32_t', 1)
    assert sg.user_tick() == 1
