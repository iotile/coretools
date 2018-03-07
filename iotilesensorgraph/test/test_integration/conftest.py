"""Fixtures with different sensor graphs for testing."""
from __future__ import (absolute_import, print_function, unicode_literals)
import os.path
import pytest
from iotile.sg import DataStream, DeviceModel, DataStreamSelector, SlotIdentifier
from iotile.sg.parser import SensorGraphFileParser
from iotile.sg.sim import SensorGraphSimulator
from iotile.sg.optimizer import SensorGraphOptimizer


def get_path(name):
    """Get a path to a sensor graph."""
    return os.path.join(os.path.dirname(__file__), 'sensor_graphs', name)


def compile_sg(name):
    """Compile a sensor graph."""

    parser = SensorGraphFileParser()
    model = DeviceModel()

    parser.parse_file(get_path(name))
    parser.compile(model=model)
    return parser.sensor_graph


@pytest.fixture(scope='module')
def complex_gate():
    """An sg with complex gating."""

    return compile_sg('complex_gates.sgf')


@pytest.fixture(scope='module')
def complex_gate_opt():
    """Optimize the complex_gate sensor_graph."""

    model = DeviceModel()
    optimizer = SensorGraphOptimizer()

    raw_sg = compile_sg('complex_gates.sgf')
    optimizer.optimize(raw_sg, model=model)
    return raw_sg


@pytest.fixture(scope='module')
def usertick_gate():
    """An sg with complex gating using a user tick."""

    return compile_sg('user_tick.sgf')


@pytest.fixture(scope='module')
def usertick_gate_opt():
    """Optimize the user tick sensor graph."""

    model = DeviceModel()
    optimizer = SensorGraphOptimizer()

    raw_sg = compile_sg('user_tick.sgf')
    optimizer.optimize(raw_sg, model=model)
    return raw_sg
