import time
from iotile.core.hw.hwmanager import HardwareManager
from iotile.core.exceptions import ArgumentError


class VerifyDeviceStep:
    """A Recipe Step used to verify that a device is setup as expected

    Args:
        os_tag (int): Optional. Expected os tag to check against in cloud
        os_version (str): Optional. Expected os version to check against in cloud.
            format is "X.Y"
        app_tag (int): Optional. Expected app tag to check against in cloud
        app_version (str): Optional. Expected app version to check against in cloud.
            format is "X.Y"
        realtime_streams (list of int): Optional. List of expected realtime streams variables
            that should be expected upon streaming enabling. If entered in hex, should have 
            the format 0x1XXX. Example: 0x100F
        tile_versions (dict of int: str): Optional. Dictionary of addresses to expection version 
            strings with format "(X, Y, Z)". Example:  8: "(2, 11, 0)"
    """
    REQUIRED_RESOURCES = [('connection', 'hardware_manager')]

    def __init__(self, args):
        self._os_tag            = args.get('os_tag')
        self._os_version        = args.get('os_version')
        self._app_tag           = args.get('app_tag')
        self._app_version       = args.get('app_version')

        self._realtime_streams  = args.get('realtime_streams')
        self._tile_versions     = args.get('tile_versions')

    def _verify_tile_versions(self, hw):
        """Verify that the tiles have the correct versions
        """
        for tile, expected_tile_version in self._tile_versions.items():
            actual_tile_version = str(hw.get(tile).tile_version())
            if expected_tile_version != actual_tile_version:
                raise ArgumentError("Tile has incorrect firmware", tile=tile, \
                    expected_version=expected_tile_version, actual_version=actual_tile_version)

    def _verify_os_app_settings(self, hw):
        """Verify that the os and app tags/versions are set correctly
        """
        con = hw.controller()
        info = con.test_interface().get_info()
        if self._os_tag is not None:
            if info['os_tag'] != self._os_tag:
                raise ArgumentError("Incorrect os_tag", actual_os_tag=info['os_tag'],\
                        expected_os_tag=self._os_tag)
        if self._app_tag is not None:
            if info['app_tag'] != self._app_tag:
                raise ArgumentError("Incorrect app_tag", actual_os_tag=info['app_tag'],\
                        expected_os_tag=self._app_tag)
        if self._os_version is not None:
            if info['os_version'] != self._os_version:
                raise ArgumentError("Incorrect os_version", actual_os_version=info['os_version'],\
                        expected_os_version=self._os_version)
        if self._app_version is not None:
            if info['app_version'] != self._app_version:
                raise ArgumentError("Incorrect app_version", actual_os_version=info['app_version'],\
                        expected_os_version=self._app_version)

    def _verify_realtime_streams(self, hw):
        """Check that the realtime streams are being produced
        """
        print("--> Testing realtime data (takes 2 seconds)")
        time.sleep(2.1)
        reports = [x for x in hw.iter_reports()]
        reports_seen = {key: 0 for key in self._realtime_streams}

        for report in reports:
            stream_value = report.visible_readings[0].stream
            if reports_seen.get(stream_value) is not None:
                reports_seen[stream_value] += 1

        for stream in reports_seen.keys():
            if reports_seen[stream] < 2:
                raise ArgumentError("Realtime Stream not pushing any reports", stream=hex(stream), \
                    reports_seen=reports_seen[stream])

    def run(self, resources):
        hw = resources['connection'].hwman
        if self._tile_versions is not None:
            print('--> Verifying tile versions')
            self._verify_tile_versions(hw)

        if self._os_tag is not None or self._app_tag is not None:
            print('--> Verifying os/app tags and versions')
            self._verify_os_app_settings(hw)

        hw.enable_streaming()

        if self._realtime_streams is not None:
            print('--> Verifying realtime streams')
            self._verify_realtime_streams(hw)
