from iotile.cloud.cloud import IOTileCloud
from iotile.core.exceptions import ArgumentError


class SyncCloudStep:
    """A Recipe Step used to synchronize the device with the POD

    Checks if the cloud settings are properly set.

    Args:
        uuid (int): Target Device
        device_template (str): Optional. Device template name to change to in cloud
        sensorgraph (str): Optional. Sensorgraph name to change to in cloud
        expected_os_tag (str): Optional. Expected os tag to check against in cloud
        expected_app_tag (str): Optional. Expected app tag to check against in cloud
        overwrite (bool): Default to False. Raises an error if the device template and sensorgraph
            is not what you expect if overwrite if False, overwise it will update the cloud
    """
    def __init__(self, args):
        if args.get('uuid') is None:
            raise ArgumentError("LoadSensorGraphStep Parameter Missing", parameter_name='uuid')

        self._uuid              = args['uuid']

        self._device_template   = args.get('device_template')
        self._expected_os_tag   = args.get('expected_os_tag')

        self._sensorgraph       = args.get('sensorgraph')
        self._expected_app_tag  = args.get('expected_app_tag')

        self._overwrite         = args.get('overwrite', False)

    def run(self):
        cloud = IOTileCloud()
        info = cloud.device_info(self._uuid)

        if self._sensorgraph is not None:
            if info['sg'] != self._sensorgraph:
                if not self._overwrite:
                    raise ArgumentError("Cloud has incorrect sensorgraph setting", \
                        cloud_sensorgraph=info['sg'], expect_sensorgraph=self._sensorgraph)
                else:
                    print("--> Updating cloud sensorgraph from %s to %s" % \
                        (info['sg'], self._sensorgraph))
                    cloud.set_sensorgraph(self._uuid, self._sensorgraph, app_tag=self._expected_app_tag)

        if self._device_template is not None:
            if info['template'] != self._device_template:
                if not self._overwrite:
                    raise ArgumentError("Cloud has incorrect device_template setting", \
                        cloud_device_template=info['template'], expect_device_template=self._device_template)
                else:
                    print("--> Updating cloud device template from %s to %s" % \
                        (info['template'], self._device_template))
                    cloud.set_device_template(self._uuid, self._device_template, os_tag=self._expected_os_tag)
