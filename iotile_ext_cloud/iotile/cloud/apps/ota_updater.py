import logging
import urllib.request
from datetime import datetime
import operator

from iotile.core.hw import IOTileApp
from iotile.core.dev.semver import SemanticVersion
from iotile.cloud import IOTileCloud, device_id_to_slug
from typedargs.annotate import docannotate, context


op_map = {">=": operator.lt,
           "gteq": operator.lt,
           "<=": operator.gt,
           "lteq": operator.gt,
           ">": operator.le,
           "gt": operator.le,
           "<": operator.ge,
           "lt": operator.ge,
           "==": operator.ne,
           "eq": operator.ne
          }


def _download_ota_script(script_url):
    """Download the script from the cloud service and store to temporary file location"""

    try:
        urllib.request.urlretrieve(script_url, "temp.trub")
        return "temp.trub"
    except Exception as e:
        print("Failed to download OTA script")
        print(e)
        return False


@context("OtaUpdater")
class OtaUpdater(IOTileApp):
    """An IOtile app that can get OTA updates from the cloud and apply them to the device.
    The primary function is a bundled "check_and_update" that

    (1) Checks the cloud for deployment requests
    (2) Grabs the most recent one for this device (if there are multiple)
    (3) Checks that the update is applicable (version)
    (4) Downloads the update script
    (5) Attempts an update
    (6) Informs the cloud of results

    Args:
        hw (HardwareManager): A HardwareManager instance connected to a
            matching device.
        app_info (tuple): The app_tag and version of the device we are
            connected to.
        os_info (tuple): The os_tag and version of the device we are
            connected to.
        device_id (int): The UUID of the device that we are connected to.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, hw, app_info, os_info, device_id):
        super(OtaUpdater, self).__init__(hw, app_info, os_info, device_id)

        self.app_info = app_info
        self.os_info = os_info

        self._cloud = IOTileCloud()
        self._con = self._hw.get(8, basic=True)

        self.dev_slug = self._get_uuid()

    @classmethod
    def AppName(cls):
        return 'ota_updater'

    def _get_uuid(self):
        device_id, = self._con.rpc(0x10, 0x08, result_format="L16x")
        return device_id_to_slug(device_id)

    @docannotate
    def check_and_update(self):
        """
        Checks the cloud for an available OTA update and applies it to the device.
        Informs the cloud of the attempt afterwards
        Gives some diagnostic info to the user as process goes

        :return: None
        """

        script = self.check_cloud_for_script()
        if not script:
            print("no OTA pending")
            return

        print("Applying deployment ", script[0])

        print("Downloading script")
        print(script[1])
        filename = _download_ota_script(script[1])

        if not filename:
            print("Download of script failed for some reason")
            return

        print("Applying script")
        status = self._apply_ota_update(filename=filename)

        if status is False:
            print("OTA update application failed")

        print("Informing cloud of OTA status")
        try:
            self._inform_cloud(script[0], self.dev_slug, status)
        except Exception as e:
            print("Failed to inform the cloud of an update attempt -- please report the error:")
            print(e)

    def check_cloud_for_script(self):
        """Checks OTA device API for latest deployment that matches the device target settings"""
        requests = self._cloud.api.ota.device(self.dev_slug).get()

        if not requests['deployments']:
            return

        latest_request = requests['deployments'][-1]
        print(latest_request)

        if latest_request['completed_on'] is not None:
            print("latest request completed")
            return False

        for criteria in latest_request['selection_criteria']:
            text, operator, value = criteria.split(":")

            if text == 'os_tag':
                if self.os_info[0] != int(value):
                    print("os_tag doesn't match: ", str(self.os_info[0]), " != ", value)
                    return False

            elif text == 'app_tag':
                if self.app_info[0] != int(value):
                    print("app_tag doesn't match: ", str(self.app_info[0]), " != ", value)
                    return False

            elif text == 'os_version':
                ver = SemanticVersion.FromString(value)
                if op_map[operator](self.os_info[1], ver):
                    return False

            elif text == 'app_version':
                ver = SemanticVersion.FromString(value)
                if op_map[operator](self.app_info[1], ver):
                    return False

            elif text == 'controller_hw_tag':
                #TODO : figure out what the check here should be
                if operator not in ('eq', '=='):
                    print("op needed: eq, op seen: ", operator)
                    return False
                if self._con.hardware_version() != value:
                    return False
            else:
                print("Unrecognized selection criteria tag : ", text)
                return False

        script = latest_request['script']
        deployment_id = latest_request['id']
        script_details = self._cloud.api.ota.script(script).file.get()
        script_url = script_details['url']
        return deployment_id, script_url

    def _apply_ota_update(self, filename="temp.trub"):
        """"Attempt to apply script to device using the device_updater app"""

        updater = self._hw.app(name='device_updater')
        try:
            updater.load_script(filename, confirm=False)
            return True
        except Exception as e:
            print("Update failed to apply to device")
            print(e)
            return False

    @docannotate
    def _inform_cloud(self, deployment_id, device_slug, attempt_result_bool):
        """ Inform cloud of results """

        now = datetime.now()
        attempt_str = "{}-{}-{}".format(now.year, now.month, now.day)

        payload = {"deployment": deployment_id,
                   "device": device_slug,
                   "attempt_successful": attempt_result_bool,
                   "last_attempt_on": attempt_str}

        self._cloud.api.ota.action.post(payload)
