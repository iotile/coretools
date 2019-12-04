"""Configure marks to allow running actual hardware tests on computers with dongles."""

import pytest

def pytest_addoption(parser):
    parser.addoption("--hardware", action="store_true", dest="hardware",
                     help="run tests that need access to bled112 hardware (2 dongles required)")


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "hardware(name): mark test to run only when hardware is available"
    )


def pytest_runtest_setup(item):
    for _ in item.iter_markers(name="hardware"):
        if item.config.getoption('hardware') is False:
            pytest.skip("integration test requires external hardware and --hardware argument")
