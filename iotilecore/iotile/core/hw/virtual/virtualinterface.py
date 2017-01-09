"""Virtual interfaces are ways to connect to a virtual IOTile device like a real one

Virtual things are different from Mock things in that mock things are designed specifically
to facilitate unit testing and hence do not allow for the complete configurability of behavior.
Virtual things are designed to allow the same level of configurability and robustness as a real
thing. 
"""

from Queue import Queue, Empty
import logging
from iotile.core.exceptions import ArgumentError
import audit

class VirtualIOTileInterface(object):
    """A virtual interface that presents an IOTile device to the world

    An example of a virtual interface is a bluetooth adapter configured with
    a GATT server that implements the TileBus over BLE protocol allowing any
    BLE client to connect to this virtual IOTile device as if it were a real
    one.

    Args:
        device (VirtualIOTileDevice): The actual device implementation that this
            virtual interface is providing access to.
    """

    def __init__(self):
        self.device = None
        self.audit_logger = logging.getLogger('virtual.audit')
        self.audit_logger.addHandler(logging.NullHandler())

        self.actions = Queue()
        self.reports = Queue()
        self.in_progress_report = None

    def start(self, device):
        """Begin allowing connections to a virtual IOTile device
        
        Args:
            device (VirtualIOTileDevice): The python object that implements the IOTile
                device functionality that we wish to allow interaction with.
        """

        raise NotImplementedError("VirtualIOTileInterface subclass did not override start")

    def process(self):
        """Process all pending actions, needs to be called periodically after start

        This function will block for up to 100 ms so that it may be simple called in a tight
        while loop without pegging the CPU to 100%.
        """

        try:
            while True:
                func, args = self.actions.get(timeout=0.1)
                func(*args)
        except Empty:
            pass

    def stop(self):
        """Stop allowing connections to this virtual IOTile device
        """
        
        raise NotImplementedError("VirtualIOTileInterface subclass did not override start")

    def _audit(self, event, **args):
        """Log an audit event with the given message and parameters

        Args:
            event (string): The event type that we are logging
            **args (dict): All required and any desired optional parameters associated
                with the audit event
        """

        if not hasattr(audit, event):
            raise ArgumentError("Unknown audit event name", name=event)

        audit_evt = getattr(audit, event)

        if len(args) > 0:
            self.audit_logger.info(audit_evt.message, args, extra={'event_name': audit_evt.name})
        else:
            self.audit_logger.info(audit_evt.message, extra={'event_name': audit_evt.name})

    def _defer(self, action, args=None):
        """Queue an action to be executed the next time process is called

        This is very useful for callbacks that should be called on the main thread but are queued
        from a different thread.

        Args:
            action (callable): A function to be called as action(*args)
            args (list): A list of arguments (possibly empty) to be passed to action
        """

        if args is None:
            args = []

        self.actions.put((action, args))

    def _queue_reports(self, *reports):
        """Queue reports for transmission over the streaming interface

        The primary reason for this function is to allow for a single implementation
        of encoding and chunking reports for streaming.

        Args:
            *reports (list): A list of IOTileReport objects that should be sent over
                the streaming interface.
        """

        for report in reports:
            self.reports.put(report)

    def _next_streaming_chunk(self, max_size):
        """Get the next chunk of data that should be streamed

        Args:
            max_size (int): The maximum size of the chunk to be returned

        Returns:
            bytearray: the chunk of raw data with size up to but not exceeding
                max_size.
        """

        chunk = bytearray()
        
        while len(chunk) < max_size:
            desired_size = max_size - len(chunk)

            #If we don't have an in progress report at the moment, attempt to get one
            if self.in_progress_report is None:
                try:
                    next_report = self.reports.get_nowait()
                except Empty:
                    return chunk

                self._audit('ReportStreamed', report=str(next_report))
                self.in_progress_report = bytearray(next_report.encode())

            if len(self.in_progress_report) <= desired_size:
                chunk += self.in_progress_report
                self.in_progress_report = None
            else:
                remaining = self.in_progress_report[desired_size:]
                chunk += self.in_progress_report[:desired_size]

                self.in_progress_report = remaining

        return chunk
