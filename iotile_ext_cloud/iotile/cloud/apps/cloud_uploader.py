"""An IOTileApp that uploads reports from an iotile device to the cloud."""

import logging
import time
import struct
from builtins import range
from iotile.core.exceptions import HardwareError, ArgumentError
from iotile.core.hw import IOTileApp
from iotile.core.hw.reports import SignedListReport
from iotile.core.utilities.console import ProgressBar
from iotile.cloud import IOTileCloud, device_id_to_slug
from typedargs.annotate import docannotate, context


@context("CloudUploader")
class CloudUploader(IOTileApp):
    """An IOtile app that can get reports from a device and upload them to the cloud.

    This app performs the same basic upload functionality as the IOTile Companion
    mobile application.  It has a single important method: upload.  This method
    will start a loop that:
        - acknowledges old data from the device that has safely reched iotile.cloud
        - triggers the device to send all of its data
        - waits for all data to be sent
        - uploads all reports to iotile.cloud

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
        super(CloudUploader, self).__init__(hw, app_info, os_info, device_id)

        self._cloud = IOTileCloud()
        self._con = self._hw.get(8, basic=True)

    @classmethod
    def AppName(cls):
        return 'cloud_uploader'

    def _get_uuid(self):
        device_id, = self._con.rpc(0x10, 0x08, result_format="L16x")
        return device_id

    def _trigger_streamer(self, index):
        error, = self._con.rpc(0x20, 0x10, index, result_format="L")

        # This error code means that the streamer did not have any new data
        if error == 0x8003801f:
            self.logger.info("We manually triggered streamer %d but it reported that there were no new readings", index)
        elif error != 0:
            raise HardwareError("Error triggering streamer", code=error, index=index)

    def _streamer_finished(self, index):
        res = self._con.rpc(0x20, 0x0a, index, result_type=(0, True))

        #Check if we got an error that means the streamer doesn't exist
        if len(res['buffer']) == 4:
            _error, = struct.unpack("<L", res['buffer'])
            return None

        comm_status, = struct.unpack("<18xBx", res['buffer'])
        return comm_status == 0

    def _wait_streamers_finished(self, timeout=60*10.0):
        start = time.time()

        while (time.time() - start) < timeout:
            for i in range(0, 16):
                self.logger.info("Waiting for streamer %d", i)
                while True:
                    status = self._streamer_finished(i)
                    if status is None:
                        self.logger.info("No streamer %d, all streamers finished", i)
                        return
                    elif status is True:
                        break

                    time.sleep(1.0)

                self.logger.info("Streamer %d finished", i)

        raise HardwareError("Device took too long to stream data", timeout_seconds=timeout)

    def _ack_streamer(self, index, value):
        if index <= 0xFF:
            error, = self._con.rpc(0x20, 0x0f, index, 0, value, arg_format="HHL", result_format="L")

            if error == 0x8003801e:
                # This means the streamer value is older than what is already there, this is not an error
                pass
            elif error:
                raise HardwareError("Error acknowledging streamer", error_code=error, index=index, value=value)
        else:
            raise ArgumentError("Streamer index is out of bounds", index=index)

    def _wait_finished_streaming(self):
        time.sleep(1.0)
        self._wait_streamers_finished()

    def download(self, trigger=None, acknowledge=True):
        """Synchronously download all reports from the device.

        This function will:
        - acknowledge old data from the device that has safely reached iotile.cloud
          unless you pass acknowledge=False
        - trigger the device to send all of its data.  This happens automatically
          when we enable_streaming.  However, if you need to manually trigger a
          streamer, you can specify that using trigger=X where X is in the index
          of the streamer to trigger.
        - wait for all data to be received from the device.

        The only differnce between this function and upload is that this function
        will return the reports as a list, rather than uploading them directly
        to iotile.cloud.

        Args:
            trigger (int): If you need to manually trigger a streamer on the device,
                you can specify its index here and it will have trigger_streamer called
                on it before we enter the upload loop.
            acknowledge (bool): If you don't want to send all cloud acknowledgements
                down to the device before enabling streaming, you can pass False.  The
                default behavior is True.

        Returns:
            list of IOTileReport: The list of reports received from the device.
        """

        device_id = self._get_uuid()
        slug = device_id_to_slug(device_id)

        self.logger.info("Connected to device 0x%X", device_id)

        if acknowledge:
            self.logger.info("Getting acknowledgements from cloud for slug %s", slug)

            resp = self._cloud.api.streamer.get(device=slug)
            acks = resp.get('results', [])
            self.logger.info("Found %d acknowledgements", len(acks))

            for ack in acks:
                index = ack['index']
                last_id = ack['last_id']

                if index <= 0xFF:
                    self.logger.info("Acknowledging highest ID %d for streamer %d", last_id, index)
                    self._ack_streamer(index, last_id)
                else:
                    raise ArgumentError("Streamer Index is Out of Range.", index=index)
        else:
            self.logger.info("Not acknowledging readings from cloud per user request")

        # Configure Downloader to not break up the report
        self.set_report_size()  #Set to max report size
        self._hw.enable_streaming()

        if trigger is not None:
            self.logger.info("Explicitly triggering streamer %d", trigger)
            self._trigger_streamer(trigger)

        self._wait_streamers_finished()

        reports = [x for x in self._hw.iter_reports()]
        signed_reports = [x for x in reports if isinstance(x, SignedListReport)]

        self.logger.info("Received %d signed reports, ignored %d realtime reports", len(signed_reports), len(reports) - len(signed_reports))

        return signed_reports

    @docannotate
    def upload(self, trigger=None, acknowledge=True):
        """Synchronously get all data from the device and upload it to iotile.cloud.

        This function will:
        - acknowledge old data from the device that has safely reached iotile.cloud
          unless you pass acknowledge=False
        - trigger the device to send all of its data.  This happens automatically
          when we enable_streaming.  However, if you need to manually trigger a
          streamer, you can specify that using trigger=X where X is in the index
          of the streamer to trigger.
        - wait for all data to be received from the device.
        - upload all reports to iotile.cloud securely.

        If you want to see details about what is happening, you can capture the
        logging output.

        This method will use whatever the default iotile.cloud domain and credentials
        are that are configured in your current virtualenv.

        Args:
            trigger (int): If you need to manually trigger a streamer on the device,
                you can specify its index here and it will have trigger_streamer called
                on it before we enter the upload loop.
            acknowledge (bool): If you don't want to send all cloud acknowledgements
                down to the device before enabling streaming, you can pass False.  The
                default behavior is True.
        """

        signed_reports = self.download(trigger, acknowledge)

        for report in signed_reports:
            self.logger.info("Uploading report with ids in (%d, %d)", report.lowest_id, report.highest_id)
            self._cloud.upload_report(report)

    @docannotate
    def get_report_size(self):
        """ Sets and verifies the report size for a pod
        Returns:
           int: The maximum size of a report
        """
        maxpacket, _comp1, comp2, = self._con.rpc(0x0A, 0x06, result_format="LBB")
        return maxpacket

    @docannotate
    def set_report_size(self, size=0xFFFFFFFF):
        """ Sets and verifies the report size for a pod
        Args:
            size (int): The maximum size of a report
        """

        error, = self._con.rpc(0x0A, 0x05, size, 0, arg_format="LB", result_format="L")

        if error:
            raise HardwareError("Error setting report size.", error_code=error, size=size)

        maxpacket, _comp1, comp2, = self._con.rpc(0x0A, 0x06, result_format="LBB")

        if maxpacket != size:
            raise HardwareError("Max Packet Size was not set as expected")



