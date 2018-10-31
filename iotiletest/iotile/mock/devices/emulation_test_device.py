from past.builtins import basestring
from iotile.emulate import EmulatedDevice
from iotile.core.hw.virtual.virtualdevice import rpc
from iotile.core.hw.proxy.proxy import TileBusProxyObject
from typedargs.annotate import context, docannotate
from iotile.core.exceptions import DataError


class TestEmulatedDevice(EmulatedDevice):
    """Basic EmulatedDevice for testing emulation.

    This device implements all of the key features of emulation
    including state saving and loading, scenario support and
    tracking changes both manually and automatically.

    Args:
        args (dict): Device creation arguments, supported keys are
            - iotile_id: The id of this device, defaults to 1.
    """

    def __init__(self, args):
        iotile_id = args.get('iotile_id', 1)

        if isinstance(iotile_id, basestring):
            iotile_id = int(iotile_id, 16)

        super(TestEmulatedDevice, self).__init__(iotile_id, 'bscemu')

        self.tracked_counter = 0
        self.manual_counter = 0
        self._tracked_properties.add('tracked_counter')

        self.register_scenario('loaded_counters', self.loaded_counter_scenario)

    @rpc(8, 0x0004, "", "H6sBBBB")
    def controller_name(self):
        """Return the name of the controller as a 6 byte string
        """

        status = (1 << 1) | (1 << 0) #Configured and running

        return [0xFFFF, self.name, 1, 0, 0, status]

    @rpc(8, 0x8000, "L", "")
    def set_tracked_counter(self, value):
        """Set the value of tracked_counter."""

        self.tracked_counter = value

    @rpc(8, 0x8001, "L", "")
    def set_manual_counter(self, value):
        """Set the value of tracked_counter."""

        self.manual_counter = value
        self._track_change('manual_counter', value)

        return []

    def dump_state(self):
        """Dump the current state of this emulated object as a dictionary.

        Returns:
            dict: The current state of the object that could be passed to load_state.
        """

        return {
            'state_format': 'basic_test_emulated_device',
            'state_version': '1.0.0',
            'tracked_counter': self.tracked_counter,
            'manual_counter': self.manual_counter
        }

    def restore_state(self, state):
        """Restore the current state of this emulated object.

        Args:
            state (dict): A previously dumped state produced by dump_state.
        """

        state_format = state.get('state_format')
        state_version = state.get('state_version')

        if state_format != 'basic_test_emulated_device':
            raise DataError("Unsupported state format", found=state_format,
                            expected='basic_test_emulated_device')

        if state_version != '1.0.0':
            raise DataError("Unsupported state version", found=state_format, expected="1.0.0")

        self.tracked_counter = state.get('tracked_counter', 0)
        self.manual_counter = state.get('manual_counter', 0)

    def loaded_counter_scenario(self, tracked_counter, manual_counter):
        """Load in the values of both counters.

        Args:
            tracked_counter (int): The value of tracked_counter
            manual_counter (int): The value of manual_counter
        """

        self.tracked_counter = tracked_counter
        self.manual_counter = manual_counter



@context("TestEmulatedDevice")
class TestEmulatedDeviceProxy(TileBusProxyObject):
    """A simply proxy object to correspond with TestEmulatedDevice."""

    @classmethod
    def ModuleName(cls):
        return 'bscemu'

    @docannotate
    def set_tracked_counter(self, value):
        """Set the value of the automatically tracked counter.

        Args:
            value (int): The value to set
        """

        self.rpc(0x80, 0x00, value, arg_format="L")

    @docannotate
    def set_manual_counter(self, value):
        """Set the value of the manually tracked counter.

        Args:
            value (int): The value to set
        """

        self.rpc(0x80, 0x01, value, arg_format="L")
