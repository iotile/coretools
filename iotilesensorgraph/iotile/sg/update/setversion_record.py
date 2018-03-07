from __future__ import unicode_literals, absolute_import, print_function
import struct
from future.utils import python_2_unicode_compatible
from iotile.core.hw.update.record import MatchQuality
from iotile.core.hw.update.records import SendErrorCheckingRPCRecord
from iotile.core.exceptions import ArgumentError


@python_2_unicode_compatible
class SetDeviceTagRecord(SendErrorCheckingRPCRecord):
    """Set the device's app or os tag and version.

    Args:
        app_tag (int): The app tag we wish to set
        app_version (str): The X.Y version that we wish to set for the app
        os_tag (int): The os tag we wish to set
        os_version (str): The X.Y os version we wish to set
    """

    RPC_ID = 0x100B

    def __init__(self, app_tag=None, app_version=None, os_tag=None, os_version=None):
        update_app = app_tag is not None
        update_os = os_tag is not None

        if app_version is None:
            app_version = "0.0"
        if os_version is None:
            os_version = "0.0"

        app_info = _combine_info(app_tag, app_version)
        os_info = _combine_info(os_tag, os_version)

        payload = struct.pack("<LLBB", os_info, app_info, int(update_os), int(update_app))

        self.update_app = update_app
        self.update_os = update_os
        self.app_tag = app_tag
        self.app_version = app_version
        self.os_tag = os_tag
        self.os_version = os_version

        super(SetDeviceTagRecord, self).__init__(8, SetDeviceTagRecord.RPC_ID, payload, response_size=4)

    @classmethod
    def MatchQuality(cls, record_data, record_count=1):
        """Check how well this record matches the given binary data.

        This function will only be called if the record matches the type code
        given by calling MatchType() and this functon should check how well
        this record matches and return a quality score between 0 and 100, with
        higher quality matches having higher scores.  The default value should
        be MatchQuality.GenericMatch which is 50.  If this record does not
        match at all, it should return MatchQuality.NoMatch.

        Many times, only a single record type will match a given binary record
        but there are times when multiple different logical records produce
        the same type of record in a script, such as set_version and
        set_userkey both producing a call_rpc record with different RPC
        values.  The MatchQuality method is used to allow for rich decoding
        of such scripts back to the best possible record that created them.

        Args:
            record_data (bytearay): The raw record that we should check for
                a match.
            record_count (int): The number of binary records that are included
                in record_data.

        Returns:
            int: The match quality between 0 and 100.  You should use the
                constants defined in MatchQuality as much as possible.
        """

        if record_count > 1:
            return MatchQuality.NoMatch

        cmd, _address, _resp_length, payload = cls._parse_rpc_info(record_data)

        if cmd == cls.RPC_ID:
            try:
                _os_info, _app_info, update_os, update_app = struct.unpack("<LLBB", payload)
                update_os = bool(update_os)
                update_app = bool(update_app)

                # TODO: Support setting os and app version at the same time
                if update_os and update_app:
                    return MatchQuality.NoMatch

            except ValueError:
                return MatchQuality.NoMatch

            return MatchQuality.PerfectMatch

        return MatchQuality.NoMatch

    @classmethod
    def FromBinary(cls, record_data, record_count=1):
        """Create an UpdateRecord subclass from binary record data.

        This should be called with a binary record blob (NOT including the
        record type header) and it will decode it into a SetDeviceTagRecord.

        Args:
            record_data (bytearray): The raw record data that we wish to parse
                into an UpdateRecord subclass NOT including its 8 byte record header.
            record_count (int): The number of records included in record_data.

        Raises:
            ArgumentError: If the record_data is malformed and cannot be parsed.

        Returns:
            SetDeviceTagRecord: The decoded reflash tile record.
        """

        _cmd, _address, _resp_length, payload = cls._parse_rpc_info(record_data)

        try:
            os_info, app_info, update_os, update_app = struct.unpack("<LLBB", payload)
            update_os = bool(update_os)
            update_app = bool(update_app)

            if update_app and not update_os:
                tag, version = _parse_info(app_info)
                return SetDeviceTagRecord(app_tag=tag, app_version=version)
            elif update_os and not update_app:
                tag, version = _parse_info(os_info)
                return SetDeviceTagRecord(os_tag=tag, os_version=version)
            else:
                raise ArgumentError("Setting app and os version at the same time not yet supported")

        except ValueError:
            raise ArgumentError("Could not parse set device version payload", payload=payload)

    def __str__(self):
        if self.update_app:
            return "Set device app to (tag:%d version:%s)" % (self.app_tag, self.app_version)

        return "Set device os to (tag:%d, version:%s)" % (self.os_tag, self.os_version)


def _parse_info(combined_info):
    tag = combined_info & ((1 << 20) - 1)

    major = combined_info >> 26 & ((1 << 6) - 1)
    minor = combined_info >> 20 & ((1 << 6) - 1)

    return tag, "%d.%d" % (major, minor)


def _combine_info(tag, version):
    if version is None:
        version = "0.0"

    if tag is None:
        tag = 0

    major, _, minor = version.partition(".")

    if tag >= (1 << 20):
        raise ArgumentError("The tag number is too high.  It must fit in 20-bits", max_tag=1 << 20, tag=tag)

    if "." not in version:
        raise ArgumentError("You must pass a version number in X.Y format", version=version)

    major, _, minor = version.partition('.')
    try:
        major = int(major)
        minor = int(minor)
    except ValueError:
        raise ArgumentError("Unable to convert version string into major and minor version numbers", version=version)

    if major < 0 or minor < 0 or major >= (1 << 6) or minor >= (1 << 6):
        raise ArgumentError("Invalid version numbers that must be in the range [0, 63]", major=major, minor=minor, version_string=version)

    version_number = (major << 6) | minor
    combined_tag = (version_number << 20) | tag

    return combined_tag
