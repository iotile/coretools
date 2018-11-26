from __future__ import unicode_literals, print_function, absolute_import
from builtins import str
from iotile.core.exceptions import ArgumentError
import pkg_resources

class SyncRTCStep(object):
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
        try:
            pkg_resources.get_distribution("iotile-support-con-nrf52832-3")
        except:
            raise ArgumentError('Proxy not installed, try calling `pip install iotile-support-con-nrf52832-3`')

        hwman = resources['connection']
        con = hwman.hwman.controller()
        rtc_man = con.rtc_manager()
        try:
            rtc_man.rtc_set_time_to_now()
            print('Time currently set at %s' % rtc_man.rtc_get_timestr())
        except:
            raise ArgumentError('Error setting RTC time, check if controller actually has RTC')