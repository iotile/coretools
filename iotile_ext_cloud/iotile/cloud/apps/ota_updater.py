import logging
from datetime import datetime
import operator

from iotile.core.hw import IOTileApp
from iotile.core.hw.update import UpdateScript
from iotile.core.dev.semver import SemanticVersion
from iotile.cloud import IOTileCloud, device_id_to_slug
from iotile_cloud.utils.basic import datetime_to_str
from typedargs.annotate import docannotate, context
from typedargs import iprint
import requests

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
        blob = requests.get(script_url, stream=True)
        return blob.content
    except Exception as e:
        iprint("Failed to download OTA script")
        iprint(e)
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
        """

        script = self.check_cloud_for_script()
        if not script:
            iprint("no OTA pending")
            return

        iprint("Applying deployment " + str(script[0]))

        iprint("Downloading script")
        iprint(script[1])
        blob = _download_ota_script(script[1])

        if not blob:
            iprint("Download of script failed for some reason")
            return

        iprint("Applying script")
        try:
            self._apply_ota_update(blob=blob)
            self._inform_cloud(script[0], self.dev_slug, True)
        except Exception:
            self._inform_cloud(script[0], self.dev_slug, False)
            raise


    def _check_criteria(self, criterion):

        for criteria in criterion:
            text, opr, value = criteria.split(":")
            if text == 'os_tag':
                if self.os_info[0] != int(value):
                    iprint("os_tag doesn't match: " + str(self.os_info[0]) + " != " + value)
                    return False

            elif text == 'app_tag':
                if self.app_info[0] != int(value):
                    iprint("app_tag doesn't match: " + str(self.app_info[0]) + " != " + value)
                    return False

            elif text == 'os_version':
                ver = SemanticVersion.FromString(value)
                if op_map[opr](self.os_info[1], ver):
                    iprint("os_version not compatible: " + str(self.os_info[1]) + "not" + opr + value)
                    return False

            elif text == 'app_version':
                ver = SemanticVersion.FromString(value)
                if op_map[opr](self.app_info[1], ver):
                    iprint("app_version not compatible: " + str(self.app_info[1]) + "not" + opr + value)
                    return False

            elif text == 'controller_hw_tag':
                # TODO : figure out what the check here should be
                if opr not in ('eq', '=='):
                    iprint("op needed: eq, op seen: " + opr)
                    return False
                if self._con.hardware_version() != value:
                    return False
            else:
                iprint("Unrecognized selection criteria tag : " + text)
                return None

        return True

    def check_cloud_for_script(self):
        """Checks OTA device API for latest deployment that matches the device target settings"""
        requests = self._cloud.api.ota.device(self.dev_slug).get()

        if not requests['deployments']:
            return False

        request_to_apply = None
        oldest_date = datetime.strptime('9999-12-31T00:00:00Z', "%Y-%m-%dT%H:%M:%SZ")

        for deployment in requests['deployments']:
            if (deployment['completed_on'] is None
                    and deployment['released_on'] is not None
                    and datetime.strptime(deployment['released_on'], "%Y-%m-%dT%H:%M:%SZ") < oldest_date
                    and self._check_criteria(deployment['selection_criteria'])):

                request_to_apply = deployment
                oldest_date = datetime.strptime(deployment['released_on'], "%Y-%m-%dT%H:%M:%SZ")

        if not request_to_apply:
            return False

        script = request_to_apply['script']
        deployment_id = request_to_apply['id']
        script_details = self._cloud.api.ota.script(script).file.get()
        script_url = script_details['url']
        return deployment_id, script_url

    def _apply_ota_update(self, blob):
        """"Attempt to apply script to device using the device_updater app"""

        updater = self._hw.app(name='device_updater')
        update_script = UpdateScript.FromBinary(blob)
        updater.run_script(update_script)

    def _inform_cloud(self, deployment_id, device_slug, attempt_result_bool):
        """ Inform cloud of results """

        now = datetime.now()
        attempt_str = datetime_to_str(now)

        payload = {"deployment": deployment_id,
                   "device": device_slug,
                   "attempt_successful": attempt_result_bool,
                   "last_attempt_on": attempt_str}

        self._cloud.api.ota.action.post(payload)
