"""Configuration object describing a streamer."""

from collections import namedtuple
from iotile.core.hw.reports import IndividualReadingReport, BroadcastReport, SignedListReport
from iotile.core.exceptions import ArgumentError, InternalError
from iotile.sg.exceptions import StreamEmptyError

StreamerReport = namedtuple("StreamerReport", ['report', 'num_readings', 'highest_id'])


class DataStreamer:
    """In charge of streaming data remotely from a device via a communication tile.

    DataStreamers are created to listen for data from a stream, package it using some
    packaging scheme and then attempt to send it remotely when triggered (possibly
    automatically by the presence of data).  They can be configured to keep trying to
    send data until it is accepted by the other side.

    Args:
        selector (DataStreamSelector): The selector that chooses what readings will be
            streamed.
        dest_tile (SlotIdentifier): The destination tile that we will stream data to
        report_format (str): A string constant defined in DataStreamer.KnownFormats
        automatic (bool): Whether the streamer should trigger whenever there is data
            or wait until it is manually triggered
        report_type (str): A string constant defined in DataStreamer.KnownTypes
        with_other (int): The index of another streamer that this streamer should
            use to know when to trigger.  Defaults to None in which case the streamer
            triggers on its own.  The combination of automatic and with_other cannot
            be specified.
        sensor_log (SensorLog): Actually create a StreamWalker to go along with this
            streamer so that we can check if it's triggered.
    """

    KnownTypes = {u'broadcast': 1, u'telegram': 1 << 1, u'synchronous': 1 << 2}
    KnownTypeCodes = {y: x for x, y in KnownTypes.items()}
    KnownFormats = {u'individual': 0, u'hashedlist': 1, u'signedlist_userkey': 2, u'signedlist_devicekey': 3}
    KnownFormatCodes = {y: x for x, y in KnownFormats.items()}

    def __init__(self, selector, dest_tile, report_format, automatic, report_type=u'telegram', with_other=None, sensor_log=None):
        report_format = str(report_format)
        report_type = str(report_type)

        if report_format not in DataStreamer.KnownFormats:
            raise ArgumentError("Unknown report format in DataStreamer constructor", report_format=report_format, known_formats=DataStreamer.KnownFormats.keys())

        if report_type not in DataStreamer.KnownTypes:
            raise ArgumentError("Unknown report type in DataStreamer constructor", report_type=report_type, known_types=DataStreamer.KnownTypes.keys())

        self.selector = selector
        self.dest = dest_tile
        self.format = report_format
        self.automatic = automatic
        self.report_type = report_type
        self.with_other = with_other
        self.walker = None
        self.index = None
        self._sensor_log = None

        if sensor_log is not None:
            self.link_to_storage(sensor_log)

    def link_to_storage(self, sensor_log):
        """Attach this DataStreamer to an underlying SensorLog.

        Calling this method is required if you want to use this DataStreamer
        to generate reports from the underlying data in the SensorLog.

        You can call it multiple times and it will unlink itself from any
        previous SensorLog each time.

        Args:
            sensor_log (SensorLog): Actually create a StreamWalker to go along with this
                streamer so that we can check if it's triggered.
        """

        if self.walker is not None:
            self._sensor_log.destroy_walker(self.walker)
            self.walker = None

        self.walker = sensor_log.create_walker(self.selector)
        self._sensor_log = sensor_log

    def has_data(self):
        """Check whether there is any data in this streamer.

        Returns:
            bool: Whether there is any available data.
        """

        if self.walker is None:
            raise InternalError("You can only check if a streamer is triggered if you create it with a SensorLog")

        return self.walker.count() > 0

    def triggered(self, manual=False):
        """Check if this streamer should generate a report.

        Streamers can be triggered automatically whenever they have data
        or they can be triggered manually. This method returns True if the
        streamer is currented triggered.

        A streamer is triggered if it:
          - (has data AND is automatic) OR
          - (has data AND is manually triggered)

        Args:
            manual (bool): Indicate that the streamer has been manually triggered.

        Returns:
            bool: Whether the streamer can generate a report right now.
        """

        if self.walker is None:
            raise InternalError("You can only check if a streamer is triggered if you create it with a SensorLog")

        if not self.automatic and not manual:
            return False

        return self.has_data()

    def requires_id(self):
        """Whether this streamer produces reports that require a report id.

        Returns:
            bool
        """

        return self.format != u'individual'

    def requires_signing(self):
        """Whether this streamer produces reports that require a valid auth_chain for signing.

        Returns:
            bool
        """

        return self.format in (u'signedlist_userkey', u'signedlist_devicekey')

    def build_report(self, device_id, max_size=None, device_uptime=0, report_id=None, auth_chain=None):
        """Build a report with all of the readings in this streamer.

        This method will produce an IOTileReport subclass and, if necessary,
        sign it using the passed authentication chain.

        Args:
            device_id (int): The UUID of the device to generate a report for.
            max_size (int): Optional maximum number of bytes that the report can be
            device_uptime (int): The device's uptime to use as the sent timestamp of the report
            report_id (int): The report id to use if the report type require serialization.
            auth_chain (AuthChain): An auth chain class to use to sign the report if the report
                type requires signing.

        Returns:
            StreamerReport: The report, its highest id and the number of readings in it.

            The highest reading id and number of readings are returned
            separately from the report itself because, depending on the format
            of the report (such as whether it is encrypted or does not contain
            reading ids), these details may not be recoverable from the report
            itself.

        Raises:
            InternalError: If there was no SensorLog passed when this streamer was created.
            StreamEmptyError: If there is no data to generate a report from.  This can only happen
                if a call to triggered() returned False.
            ArgumentError: If the report requires additional metadata that was not passed like a
                signing key or report_id.
        """

        if self.walker is None or self.index is None:
            raise InternalError("You can only build a report with a DataStreamer if you create it with a SensorLog and a streamer index")

        if self.requires_signing() and auth_chain is None:
            raise ArgumentError("You must pass an auth chain to sign this report.")

        if self.requires_id() and report_id is None:
            raise ArgumentError("You must pass a report_id to serialize this report")

        if self.format == 'individual':
            reading = self.walker.pop()

            highest_id = reading.reading_id

            if self.report_type == 'telegram':
                return StreamerReport(IndividualReadingReport.FromReadings(device_id, [reading]), 1, highest_id)
            elif self.report_type == 'broadcast':
                return StreamerReport(BroadcastReport.FromReadings(device_id, [reading], device_uptime), 1, highest_id)
        elif self.format == 'hashedlist':
            max_readings = (max_size - 20 - 24) // 16
            if max_readings <= 0:
                raise InternalError("max_size is too small to hold even a single reading", max_size=max_size)

            readings = []
            highest_id = 0
            try:
                while len(readings) < max_readings:
                    reading = self.walker.pop()
                    readings.append(reading)
                    if reading.reading_id > highest_id:
                        highest_id = reading.reading_id
            except StreamEmptyError:
                if len(readings) == 0:
                    raise

            return StreamerReport(SignedListReport.FromReadings(device_id, readings, report_id=report_id, selector=self.selector.encode(),
                                                                streamer=self.index, sent_timestamp=device_uptime), len(readings), highest_id)

        raise InternalError("Streamer report format or type is not supported currently", report_format=self.format, report_type=self.report_type)

    def __str__(self):
        manual = "manual " if not self.automatic else ""
        if self.report_type == 'broadcast':
            type_string = 'broadcast '
        elif self.format == 'individual':
            type_string = 'realtime '
        else:
            type_string = ""

        security = ""
        if self.format == 'signedlist_userkey':
            security = "signed "

        to_slot = ""
        if not self.dest.controller:
            to_slot = " to " + str(self.dest)

        #FIXME: Make sure we generate the right code for streamer type

        with_statement = ""
        if self.with_other is not None:
            with_statement = " with streamer %d" % self.with_other

        template = "{manual}{security}{report_type}streamer on {selector}{to_slot}{with_other}"
        return template.format(manual=manual, security=security, report_type=type_string, selector=self.selector,
                               with_other=with_statement, to_slot=to_slot)

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        if not isinstance(other, DataStreamer):
            return NotImplemented

        return (self.selector == other.selector and self.dest == other.dest and
                self.automatic == other.automatic and self.report_type == other.report_type and
                self.with_other == other.with_other)

    def __ne__(self, other):
        if not isinstance(other, DataStreamer):
            return NotImplemented

        return not self == other
