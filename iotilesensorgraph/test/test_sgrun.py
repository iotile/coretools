"""Tests to make sure the iotile-sgrun command line tool is not broken."""


import sys
import os.path
import pytest
from iotile.sg.scripts.iotile_sgrun import main


class SystemExitError(Exception):
    """Internal error to signal that sys.exit was called."""
    pass

@pytest.fixture
def exitcode(monkeypatch):
    """Patch sys.exit so we can test argparse containing code."""

    def _fake_exit(code):
        raise SystemExitError(code)

    monkeypatch.setattr(sys, 'exit', _fake_exit)


def test_basic_help(exitcode):
    """Make sure the program can print help text."""

    with pytest.raises(SystemExitError):
        main(['--help'])


def test_basic_simulation(exitcode):
    """Make sure we can run a simulation to completion."""

    infile = os.path.join(os.path.dirname(__file__), 'sensor_graphs', 'basic_block.sgf')

    retval = main(['-s', 'run_time 1 second', infile])
    assert retval == 0
