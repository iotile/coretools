"""Test coverage of the ReferenceDevice and ReferenceController emulated objects."""

from iotile.core.hw import HardwareManager

def test_basic_usage():
    """Make sure we can import and use the objects."""

    with HardwareManager(port='emulated:reference_1_0') as hw:
        hw.connect(1)
        debug = hw.debug()

        state = debug.dump_snapshot()
        debug.restore_snapshot(state)
