"""Test coverage of the ReferenceDevice and ReferenceController emulated objects."""

from iotile.core.hw import HardwareManager
from iotile.emulate.virtual import EmulatedPeripheralTile

from iotile.sg.virtual import ReferenceDevice

def test_basic_usage():
    """Make sure we can import and use the objects."""

    with HardwareManager(port='emulated:reference_1_0') as hw:
        hw.connect(1)
        debug = hw.debug()

        state = debug.dump_snapshot()
        debug.restore_snapshot(state)


def test_peripheral_tiles():
    """Make sure the controller tile properly brings up the peripheral tiles in a controlled manner."""

    device = ReferenceDevice({})
    peripheral = EmulatedPeripheralTile(10, b'abcdef', device)
    device.add_tile(10, peripheral)

    device.start()

    device.stop()
