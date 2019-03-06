from iotile.core.exceptions import ArgumentError
import pkg_resources


class SyncRTCStep:
    """Attempt to set RTC to current UTC time.

    This function requires a shared hardware manager resource to be setup
    containing a connected device that we can send the script to.

    Shared Resources:
        connection (hardware_manager): A connected hardware_manager resource
            that we can use to send our ota script down to a device.
    """

    REQUIRED_RESOURCES = [('connection', 'hardware_manager')]

    def __init__(self, args):
        pass

    def run(self, resources):
        """Sets the RTC timestamp to UTC.

        Args:
            resources (dict): A dictionary containing the required resources that
                we needed access to in order to perform this step.
        """
        hwman = resources['connection']
        con = hwman.hwman.controller()
        test_interface = con.test_interface()
        try:
            test_interface.synchronize_clock()
            print('Time currently set at %s' % test_interface.current_time_str())
        except:
            raise ArgumentError('Error setting RTC time, check if controller actually has RTC or if iotile-support-lib-controller-3 is updated')
