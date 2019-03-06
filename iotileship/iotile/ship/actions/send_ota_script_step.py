from iotile.core.hw.update import UpdateScript
from iotile.core.exceptions import ArgumentError


class SendOTAScriptStep:
    """Send a TRUB OTA script to a device and execute it.

    This function requires a shared hardware manager resource to be setup
    containing a connected device that we can send the script to.

    Shared Resources:
        connection (hardware_manager): A connected hardware_manager resource
            that we can use to send our ota script down to a device.

    Args:
        file (str): The path to the target ota file that should be sent.  If
            a relative path is given, it is taken as relative to the current
            working directory.
        no_reboot (bool): Optional argument to not reboot the device
            after the OTA script has been run.  Normal behavior is to
            reboot after OTA.
    """

    REQUIRED_RESOURCES = [('connection', 'hardware_manager')]
    FILES = ['file']

    def __init__(self, args):
        if 'file' not in args:
            raise ArgumentError("SendOTAScriptStep required parameters missing", required=["file"], args=args)

        self._file = args['file']
        self._no_reboot = args.get('no_reboot', False)

        with open(self._file, "rb") as infile:
            data = infile.read()
            self._script = UpdateScript.FromBinary(data)

    def run(self, resources):
        """Actually send the trub script.

        Args:
            resources (dict): A dictionary containing the required resources that
                we needed access to in order to perform this step.
        """

        hwman = resources['connection']

        updater = hwman.hwman.app(name='device_updater')
        updater.run_script(self._script, no_reboot=self._no_reboot)
