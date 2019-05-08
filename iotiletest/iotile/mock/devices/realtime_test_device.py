"""Reference device for testing the individual report format
"""

from iotile.core.hw.exceptions import DevicePushError
from iotile.core.hw.virtual import SimpleVirtualDevice
from iotile.core.hw.reports import IndividualReadingReport, IOTileReading, BroadcastReport


class RealtimeTestDevice(SimpleVirtualDevice):
    """Mock IOTileDevice that streams and traces data periodically

    This device can be configured to stream data on any streams at any interval.
    It can be used for testing realtime streaming functionality of any other portion
    of the IOTile stack.

    If no other arguments are passed, this device defaults to producing the value 100
    on stream 0x1001 every second.  If a streams dictionary is passed, that overrides
    this default setting.

    You can also configure this device to broadcast readings without a connection on
    a periodic interval as well.

    If no 'trace' argument is passed the device defaults to tracing the phrase
    'Hello trace world.  ' every second.  If a 'trace' array is passed, that overrides
    the default behavior.

    Args:
        args (dict): Any arguments that you want to pass to create this device.
            Supported args are:

                iotile_id (int): The UUID used for this device.  If no UUID is
                    specified, the default value of 1 is used.

                streams (dict): A map of strings with hex numbers to tuples of
                    (interval, value) where interval is a float that expresses
                    how often the stream should stream in seconds and value is
                    an integer that is sent as the value every interval as a
                    realtime reading (IndividualReadingReport).  The stream id
                    is the key of the streams dict which should be a string
                    encoding of a hex number including the prefix 0x so that
                    it can be parsed with int(key, 0).

                broadcast (dict): A map of strings with hex numbers to tuples
                    of (interval, value) where interval is a float that
                    expresses how often the stream should stream in seconds
                    and value is an integer that is sent as the value every
                    interval as a broadcast reading (BroadcastReport).  The
                    stream id is the key of the streams dict which should be a
                    string encoding of a hex number including the prefix 0x so
                    that it can be parsed with int(key, 0).

                    Note that a device can only broadcast a single value at
                    once so if you specify multiple broadcast entries, only
                    the last one to be triggered will be visible at any given
                    time.  For this reason, it is not useful to have multiple
                    broadcast values with the same ``interval`` since only one
                    will ever be shown.

                trace (list): A list of tuples which are (float, string) lists
                    that will trace the fixed string every fixed interval
                    given by the first float argument in seconds.
    """

    def __init__(self, args):
        iotile_id = args.get('iotile_id', 1)

        if isinstance(iotile_id, str):
            iotile_id = int(iotile_id, 16)

        super(RealtimeTestDevice, self).__init__(iotile_id, 'Simple')

        streams = args.get('streams', {'0x1001': (1.0, 100)})
        broadcast = args.get('broadcast', {'0x1001': (1.0, 100)})

        if 'streams' in args:
            streams = args['streams']

        for key, value in streams.items():
            stream = int(key, 0)
            interval, reading = value

            self.create_worker(self._create_stream, interval, stream, reading)

        for key, value in broadcast.items():
            stream = int(key, 0)
            interval, reading = value

            self.create_worker(self._create_broadcast, interval, stream, reading)

        traces = [[1.0, 'Hello trace world.  ']]

        if 'trace' in args:
            traces = args['trace']

        for interval, value in traces:
            self.create_worker(self._create_trace, interval, value)

    async def _create_trace(self, value):
        """Send a realtime tracing value

        Args:
            value (string): The tracing value to send
        """

        if not self.interface_open('tracing'):
            return

        try:
            await self.trace(bytearray(value.encode('ascii')))
        except DevicePushError:
            pass

    async def _create_stream(self, stream, value):
        """Send a realtime streaming value

        Args:
            stream (int): The stream id to send
            value (int): The stream value to send
        """

        if not self.interface_open('streaming'):
            return

        reading = IOTileReading(0, stream, value)

        report = IndividualReadingReport.FromReadings(self.iotile_id, [reading])

        try:
            await self.stream(report)
        except DevicePushError:
            pass

    async def _create_broadcast(self, stream, value):
        """Send a broadcast streaming value.

        Args:
            stream (int): The stream id to send
            value (int): The stream value to send
        """

        reading = IOTileReading(0, stream, value)

        report = BroadcastReport.FromReadings(self.iotile_id, [reading])

        try:
            await self.stream(report)
        except DevicePushError:
            pass
