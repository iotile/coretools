"""State machine for parsing IOTile reports coming in on a streaming basis
"""

class IOTileReportParser (object):
    """Accumulates data from a stream and emits IOTileReports

    Every time new data is available on the stream, add_data should be called.
    Every time a complete report has been received, the callback passed in will
    be called with an IOTileReport subclass
    """

    def __init__(self, callback):
        self.report_callback = callback
        