"""State machine for parsing IOTile reports coming in on a streaming basis
"""

import pkg_resources
from iotile.core.exceptions import ArgumentError

class IOTileReportParser (object):
    """Accumulates data from a stream and emits IOTileReports

    Every time new data is available on the stream, add_data should be called.
    Every time a complete report has been received, the optional callback passed in will
    be called with an IOTileReport subclass.  

    Args:
        report_callback (callable): A function to be called every time a new report is received
            The signature should be bool report_callback(report, context).  The return value is True to
            indicate that IOTileReportParser should also keep a copy of the report or
            False to indicate it should delete it.
        error_callback (callable): A function to be called every time an error occurs.
            The signature should be error_callback(error_code, message, context).  If a fatal
            error occurs, further parsing of reports will be stopped.
    """

    #States for parser state machine
    WaitingForReportType = 1
    WaitingForReportHeader = 2 
    WaitingForCompleteReport = 3
    ErrorState = 4

    #Errors
    ErrorFindingReportType = 1
    ErrorParsingReportHeader = 2
    ErrorParsingCompleteReport = 3

    def __init__(self, report_callback=None, error_callback=None):
        self.report_callback = report_callback
        self.error_callback = error_callback

        self.raw_data = bytearray()
        self.state = IOTileReportParser.WaitingForReportType

        self.current_type = 0
        self.current_report_parser = None
        self.current_header_size = 0
        self.current_report_size = 0
        self.context = None

        self.known_formats = self._build_type_map()
        self.reports = []

    def add_data(self, data):
        """Add data to our stream, emitting reports as each new one is seen

        Args:
            data (bytearray): A chunk of new data to add
        """

        if self.state == self.ErrorState:
            return

        self.raw_data += bytearray(data)

        still_processing = True
        while still_processing:
            still_processing = self.process_data()

    def process_data(self):
        """Attempt to extract a report from the current data stream contents

        Returns:
            bool: True if further processing is required and process_data should be
                called again.
        """

        further_processing = False

        if self.state == self.WaitingForReportType and len(self.raw_data) > 0:
            self.current_type = self.raw_data[0]

            try:
                self.current_header_size = self.calculate_header_size(self.current_type)
                self.state = self.WaitingForReportHeader
                further_processing = True
            except Exception, exc:
                self.state = self.ErrorState

                if self.error_callback:
                    self.error_callback(self.ErrorFindingReportType, str(exc), self.context)
                else:
                    raise
        
        if self.state == self.WaitingForReportHeader and len(self.raw_data) >= self.current_header_size:
            try:
                self.current_report_size = self.calculate_report_size(self.current_type, self.raw_data[:self.current_header_size])
                self.state = self.WaitingForCompleteReport
                further_processing = True
            except Exception, exc:
                self.state = self.ErrorState

                if self.error_callback:
                    self.error_callback(self.ErrorParsingReportHeader, str(exc), self.context)
                else:
                    raise

        if self.state == self.WaitingForCompleteReport and len(self.raw_data) >= self.current_report_size:
            try:
                report_data = self.raw_data[:self.current_report_size]
                self.raw_data = self.raw_data[self.current_report_size:]

                report = self.parse_report(self.current_type, report_data)
                self._handle_report(report)
                self.state = self.WaitingForReportType
                further_processing = True
            except Exception, exc:
                self.state = self.ErrorState

                if self.error_callback:
                    self.error_callback(self.ErrorParsingCompleteReport, str(exc), self.context)
                else:
                    raise

        return further_processing

    def calculate_header_size(self, current_type):
        """Determine the size of a report header given its report type
        """

        fmt = self.known_formats[current_type]
        return fmt.HeaderLength()

    def calculate_report_size(self, current_type, report_header):
        """Determine the size of a report given its type and header
        """

        fmt = self.known_formats[current_type]
        return fmt.ReportLength(report_header)

    def parse_report(self, current_type, report_data):
        """Parse a report into an IOTileReport subclass
        """

        fmt = self.known_formats[current_type]
        return fmt(report_data)

    def _handle_report(self, report):
        """Try to emit a report and possibly keep a copy of it
        """

        keep_report = True

        if self.report_callback is not None:
            keep_report = self.report_callback(report, self.context)

        if keep_report:
            self.reports.append(report)

    @classmethod
    def _build_type_map(cls):
        """Build a map of all of the known report format processors
        """

        formats = {}

        for entry in pkg_resources.iter_entry_points('iotile.report_format'):
            report_format = entry.load()
            formats[report_format.ReportType] = report_format

        return formats

    @classmethod
    def DeserializeReport(cls, serialized):
        """Deserialize a report that has been serialized by calling report.serialize()

        Args:
            serialized (dict): A serialized report object
        """

        type_map = cls._build_type_map()

        if serialized['report_format'] not in type_map:
            raise ArgumentError("Unknown report format in DeserializeReport", format=serialized['report_format'])

        report = type_map[serialized['report_format']](serialized['encoded_report'])
        report.received_time = serialized['received_time']

        return report
