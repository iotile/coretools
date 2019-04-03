"""Mixin for keeping track of received report data."""

import functools
from ...reports import IOTileReportParser

class ReportHandlerMixin:
    """A Mixin that handling parsing IOTile reports.

    All data that is received from the IOTile device streaming
    interface can be parsed in a universal way using the
    :class:`IOTileReportParser` class.  This mixin takes care
    of managing that class per active connection and reseting
    it whenever the streaming interface is closed.

    It adds three helper methods:

    - :meth:`streaming_opened`: This method must be called whenever
        the streaming interface is opened.  It initializes the
        report parser and stores it as per-connection data.
    - :meth:`handle_streaming_data`: This method can be called
        whenever a new chunk of report data is received.  It will
        handle parsing it and sending ``report`` notifications
        whenever a complete report is received.

    .. important:

        This class assumes that it will be installed alongside
        :class:`PerConnectionDataMixin` or a compatible class.

        It relies on ``_get_property``, ``track_property`` and
        ``_get_conn_id``.

        Similarly, it assumes that a coroutine ``notify_event``
        is available to call when there is a new report received.

        Finally, it assumes that there will be a ``_logger``
        instance that can be used to log information.
    """

    def streaming_opened(self, connection_string):
        """Prepare for receiving streaming reports.

        This method must be called whenever the streaming interface on a
        device is successfully opened.  It creates a report parser for that
        device and stores it with the connection context.

        Args:
            connection_string (str): The connection string for the
                device in question.
        """

        conn_id = self._get_conn_id(connection_string)
        if conn_id is None:
            self._logger.warning("Could not find connection for device %s in streaming_opened", connection_string)
            return

        report_callback = functools.partial(_handle_report, self, self._logger,
                                            connection_string)
        error_callback = functools.partial(_handle_error, connection_string, self._logger)
        parser = IOTileReportParser(error_callback=error_callback,
                                    report_callback=report_callback)

        self._track_property(conn_id, 'report_parser', parser)

    def handle_streaming_data(self, connection_string, data):
        """Process streaming data and notify any complete reports.

        This method should be called whenever a chunk of streaming data
        is received and will accumulate data until a complete report
        is ready and then automatically notify that report.

        Args:
            connection_string (str): The connection string for the
                device in question.
            data (bytes): The next chunk of report data.
        """

        conn_id = self._get_conn_id(connection_string)
        if conn_id is None:
            self._logger.warning("Could not find connection for device %s in streaming_opened", connection_string)
            return

        parser = self._get_property(conn_id, 'report_parser')
        if parser is None:
            self._logger.warning("No report parser associated with device %s but streaming data received", connection_string)

        parser.add_data(data)


def _handle_report(adapter, _logger, conn_string, report):
    adapter.notify_event_nowait(conn_string, 'report', report)


def _handle_error(conn_string, logger, error_code, message, _context):
    logger.warning("Error (code=%d, msg=%s) parsing report on device %s",
                   error_code, message, conn_string)
