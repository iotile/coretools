"""An IOTileApp that can run an update script on a device."""

from __future__ import unicode_literals, absolute_import, print_function
from builtins import input
import time
import sys
import logging
from typedargs.annotate import context, docannotate
from typedargs import iprint, type_system
from iotile.core.exceptions import HardwareError
from iotile.core.utilities.console import ProgressBar
from .app import IOTileApp
from ..update import UpdateScript


@context("DeviceUpdater")
class DeviceUpdater(IOTileApp):
    """An app that can download and run a script on an IOTile device.

    Args:
        hw (HardwareManager): A HardwareManager instance connected to a
            matching device.
        app_info (tuple): The app_tag and version of the device we are
            connected to.
        os_info (tuple): The os_tag and version of the device we are
            connected to.
        device_id (int): The UUID of the device that we are connected to.
    """

    IdleStatus = 0
    WaitingForScript = 1
    ReceivingScript = 2
    ReceivedScript = 3
    ValidatedScript = 4
    ExecutingScript = 5

    def __init__(self, hw, app_info, os_info, device_id):
        super(DeviceUpdater, self).__init__(hw, app_info, os_info, device_id)

        self._logger = logging.getLogger(__name__)
        self._con = hw.get(8, basic=True)

    @classmethod
    def AppName(cls):
        """A unqiue name for this app so that it can be loaded by name.

        Returns:
            str: The unique name for this app module.
        """

        return 'device_updater'

    @classmethod
    def _prompt_yesno(cls, message):
        valid_answer = False

        while not valid_answer:
            resp = input(message)
            resp = resp.lower()

            if resp in ['y', 'n']:
                return resp == 'y'

            print("Please type y for yes or n for no.")

    @docannotate
    def load_script(self, script_path, confirm=True, no_reboot=False):
        """Load a script from a file and run it.

        This function will load a binary update script from the file given in
        script_path, download it to the device, run it and wait for it to
        finish.

        Any errors during script execution will be raised as HardwareError
        exceptions.

        Args:
            script_path (str): The path to the binary script file (.trub extension)
                that you wish to load.
            confirm (bool): Require explicit confirmation from an interactive user
                before running the script on the device.  This defaults to true,
                which means if you want to use this function in a batch setting.
                You need to pass confirm=False.
            no_reboot (bool): Do not reboot the device after running the script.
                You typically want to reboot so this defaults to False.  If you know
                what you are doing, you can set this to True to not do a sanity reboot
                after running the script.
        """

        with open(script_path, "rb") as infile:
            indata = infile.read()

        script = UpdateScript.FromBinary(indata)

        print("Loaded script with %d actions from file %s" % (len(script.records), script_path))
        print("Running script on device 0x%X with app info (%d %s) and os_info (%d %s)" % (self._device_id, self._app_tag, self._app_version, self._os_tag, self._os_version))

        if confirm:
            show_script = self._prompt_yesno("Do you want to see the script contents before programing (y/n)? ")

            if show_script:
                print("\nScript Actions:")
                for i, record in enumerate(script.records):
                    print("%02d: %s" % (i + 1, str(record)))

                print("")

            do_load = self._prompt_yesno("Are you sure you want to program this script (y/n)? ")
            if not do_load:
                print("Aborting device update due to user request")
                return

        status, _err = self._query_status()

        if status != self.IdleStatus and not confirm:
            print("ERROR: Loading script would require user confirmation to override an incomplete prior update.")
            return

        if status in (self.ReceivedScript, self.ReceivingScript, self.WaitingForScript):
            if status == self.ReceivedScript:
                print("There is a script currently loaded in the device that was never run.")
            elif status in (self.ReceivingScript, self.WaitingForScript):
                print("WARNING: The device is currently waiting for script data from a previous update.")
                print("         Make sure that no one else is currently connected to this device before proceeding.")

            clear = self._prompt_yesno("Do you want to clear the current script to program this one (y/n)? ")
            if not clear:
                print("Aborting device update because the device was not idle")
                return

            print("Clearing loaded script (this can take up to 10 seconds)")
            self._reset_script()
        elif status in (self.ValidatedScript, self.ExecutingScript):
            print("The device is currently running a script, you must wait for it to finish.")
            return

        self.run_script(script)

    def run_script(self, script, force=False, no_reboot=False):
        """Run a script on the connected IOTile device.

        The script must an UpdateScript object.  If you are looking for an
        interactive function that will load a script from a file and show
        update information to a user, you should use load_script. This is a
        low level function that is meant to be called from a larger program.

        If this run is called from an interactive session (inside the iotile
        tool) then it will show a progress bar during download and periodic
        updates during script execution, otherwise there is no feedback until
        the script is finished.

        Args:
            script (UpdateScript): The script that we wish to run on our attached
                device.
            force (bool): If there is already a script loaded but not yet executed,
                clear that script before proceeding.
            no_reboot (bool): Do not reboot the device after running the script.
                You typically want to reboot so this defaults to False.  If you know
                what you are doing, you can set this to True to not do a sanity reboot
                after running the script.
        """

        raw_data = script.encode()

        status, _err = self._query_status()
        if status == self.ReceivedScript and force:
            self._reset_script()
        elif status != self.IdleStatus:
            raise HardwareError("Cannot run script on a remote_bridge that is not currently idle", status=status)

        self._begin_script()

        progress = ProgressBar("Downloading script", 100)

        progress.start()
        try:
            self.push_script(raw_data, progress)
        finally:
            progress.end()

        self._end_script()
        self._wait_script()

        if not no_reboot:
            iprint("Rebooting device")
            self._reboot()

    def _begin_script(self):
        """Indicate that we are going to start loading a script."""

        err, = self._con.rpc(0x21, 0x00, result_format="L", timeout=10.0)
        return err

    def _end_script(self):
        """Indicate that we are done loading a script."""

        err, = self._con.rpc(0x21, 0x02, result_format="L")
        if err != 0:
            raise HardwareError("Error ending script", error_code=err)

    def _trigger_script(self):
        """Trigger the execution of the currently loaded script."""

        err, = self._con.rpc(0x21, 0x03, result_format="L")
        if err != 0:
            raise HardwareError("Error triggering script", error_code=err)

    def _query_status(self):
        """Query the status of script loading or execution."""

        status, error = self._con.rpc(0x21, 0x04, result_format="LL")
        return status, error

    def _reset_script(self):
        err, = self._con.rpc(0x21, 0x05, result_format="L", timeout=15.0)
        if err != 0:
            raise HardwareError("Error resetting script", error_code=err)

    def _reboot(self):
        """Reboot the device."""

        self._con.reset()

    def _wait_script(self):
        """Trigger a script and then synchronously wait for it to finish processing."""

        self._trigger_script()
        status, error = self._query_status()
        if error != 0:
            raise HardwareError("Error executing remote script", error_code=error)

        error_count = 0

        iprint("Waiting for script to validate")
        while status == 3:
            time.sleep(0.1)

            try:
                status, error = self._query_status()

                if error != 0:
                    raise HardwareError("Error executing remote script", error_code=error)
            except HardwareError:
                error_count += 1
                if error_count > 2:
                    raise HardwareError("Too many errors waiting for script to finish execution", error=str(HardwareError))

            if error != 0:
                raise HardwareError("Error executing remote script", error_code=error)

        iprint("Waiting for script to finish executing")
        while status != 0:
            if type_system.interactive:
                sys.stdout.write('.')
                sys.stdout.flush()

            # Poll until the script has finished executing.  Some scripts
            # will cause the device to reset, so if that happens, make sure
            # we don't flag that as an error and cleanly reconnect.
            time.sleep(0.1)
            try:
                status, error = self._query_status()
            except HardwareError:
                error_count += 1
                if error_count > 10:
                    if type_system.interactive:
                        sys.stdout.write('\n')

                    raise HardwareError("Too many errors waiting for script to finish execution", error=str(HardwareError))

            if error != 0:
                if type_system.interactive:
                    sys.stdout.write('\n')
                raise HardwareError("Error executing remote script", error_code=error)

        if type_system.interactive:
            sys.stdout.write('\n')

    def push_script(self, data, progress=None):
        """Push a byte array into the controller as a remote script."""

        def _update_progress(current, total):
            if progress is not None:
                progress.progress(current*100/total)

        self._con.stream.send_highspeed(data, _update_progress)
