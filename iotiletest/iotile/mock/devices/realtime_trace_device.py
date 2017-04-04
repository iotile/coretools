"""Reference device for testing realtime tracing of data
"""

from iotile.core.hw.virtual.virtualdevice import VirtualIOTileDevice


class RealtimeTracingDevice(VirtualIOTileDevice):
    """Mock IOTileDevice that traces data periodically

    This device can be configured to trace arbitrary strings at arbitrary intervals.
    If no other trace arguments are given, the device defaults to tracing the fixed
    string 'Hello trace world.  ' once per seoncd.

    Args:
        args (dict): Any arguments that you want to pass to create this device.
            Supported args are:
                iotile_id (int): The UUID used for this device (default: 1)
                trace (list): A list of tuples which are (float, string) lists
                    that will trace the fixed string every fixed interval given
                    by the first float argument in seconds.
    """

    def __init__(self, args):
        iotile_id = args.get('iotile_id', 1)

        if isinstance(iotile_id, basestring) or isinstance(iotile_id, unicode):
            iotile_id = int(iotile_id, 16)

        super(RealtimeTracingDevice, self).__init__(iotile_id, 'Simple')

        traces = [[1.0, 'Hello trace world.  ']]

        if 'trace' in args:
            traces = args['trace']

        for interval, value in traces:
            self.create_worker(self._create_trace, interval, value)

    def _create_trace(self, value):
        """Send a realtime tracing value

        Args:
            value (string): The tracing value to send
        """

        self.trace(bytearray(value.encode('ascii')))
