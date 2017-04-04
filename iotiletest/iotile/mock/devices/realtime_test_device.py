"""Reference device for testing the individual report format
"""

from iotile.core.hw.virtual.virtualdevice import VirtualIOTileDevice
from iotile.core.hw.reports import IndividualReadingReport, IOTileReading


class RealtimeStreamingDevice(VirtualIOTileDevice):
    """Mock IOTileDevice that streams data periodically

    This device can be configured to stream data on any streams at any interval.
    It can be used for testing realtime streaming functionality of any other portion
    of the IOTile stack.

    If no other arguments are passed, this device defaults to producing the value 100
    on stream 0x1001 every second.  If a streams dictionary is passed, that overrides
    this default setting.

    Args:
        args (dict): Any arguments that you want to pass to create this device.
            Supported args are:
                iotile_id (int): The UUID used for this device (default: 1)
                streams (dict): A map of strings with hex numbers to tuples of (interval, value)
                    where interval is a float that expresses how often the stream should stream
                    in seconds and value is an integer that is sent as the value every interval
                    as a realtime reading (IndividualReadingReport).  The stream id is the key of the
                    streams dict which should be a string encoding of a hex number including
                    the prefix 0x so that it can be parsed with int(key, 0)
    """

    def __init__(self, args):
        iotile_id = args.get('iotile_id', 1)

        if isinstance(iotile_id, basestring) or isinstance(iotile_id, unicode):
            iotile_id = int(iotile_id, 16)

        super(RealtimeStreamingDevice, self).__init__(iotile_id, 'Simple')

        streams = {'0x1001': (1.0, 100)}

        if 'streams' in args:
            streams = args['streams']

        for key, value in streams.iteritems():
            stream = int(key, 0)
            interval, reading = value

            self.create_worker(self._create_stream, interval, stream, reading)

    def _create_stream(self, stream, value):
        """Send a realtime streaming value

        Args:
            stream (int): The stream id to send
            value (int): The stream value to send
        """

        reading = IOTileReading(0, stream, value)

        report = IndividualReadingReport.FromReadings(self.iotile_id, [reading])
        self.stream(report)
