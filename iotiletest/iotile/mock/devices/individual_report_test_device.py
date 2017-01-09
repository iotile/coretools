"""Reference device for testing the individual report format
"""

from iotile.core.hw.virtual.virtualdevice import VirtualIOTileDevice, rpc, RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from iotile.core.exceptions import ArgumentError
from iotile.core.hw.reports.individual_format import IndividualReadingReport, IOTileReading

class IndividualReportTestDevice(VirtualIOTileDevice):
    """Mock IOTileDevice that creates a sequence of reports upon connection

    This device can be considered a reference implementation of the individual
    reading report format.

    Args:
        args (dict): Any arguments that you want to pass to create this device.
            Supported args are:
                iotile_id (int): The UUID used for this device (default: 1)
                num_readings (int): The number of readings to be generated every
                    time the streaming interface is opened. (default: 100)
                start_timestamp (int): The first timestamp that should be generated
                    for the first Reading sent.  Timestamps are sequential for each
                    reading, so x, x+1, etc.
                    Default: 0
                reading_generator (string): The method for generating readings. 
                    Options are: sequential, random (default: sequential)
                    random will generate random values between the reading_min and
                    reading_max keys (default: 0, 100)
                    sequential will sequentially generate reading values starting
                    at reading_start (default: 0)
    """

    def __init__(self, args):
        iotile_id = args.get('iotile_id', 1)

        generator = args.get('reading_generator', 'sequential')            
        self.num_readings = args.get('num_readings', 100)

        stream_string = args.get('stream_id', '5001')
        self.stream_id = int(stream_string, 0)
        
        #Now pull in args for the generator
        if generator == 'sequential':
            self.reading_start = args.get('reading_start', 0)
            self.generator = self._generate_sequential
        elif generator == 'random':
            self.reading_min = args.get('reading_min', 0)
            self.reading_max = args.get('reading_max', 100)
            self.generator = self._generate_random
        else:
            raise ArgumentError("Unknown reading generator mechanism", reading_generator=generator, known_generators=['sequential', 'random'])

        super(IndividualReportTestDevice, self).__init__(1, 'Simple')

    @rpc(8, 0x0004, "", "H6sBBBB")
    def controller_name(self):
        """Return the name of the controller as a 6 byte string
        """

        status = (1 << 1) | (1 << 0) #Configured and running
        
        return [0xFFFF, self.name, 1, 0, 0, status]

    def _generate_sequential(self):
        reports = []
        
        for i in xrange(self.reading_start, self.num_readings+self.reading_start):
            reading = IOTileReading(i-self.reading_start, self.stream_id, i)
            report = IndividualReadingReport.FromReadings(self.iotile_id, [reading])
            reports.append(report)

        return reports

    def _generate_random(self):
        return []

    def open_streaming_interface(self):
        """Called when someone opens a streaming interface to the device

        Returns:
            list: A list of IOTileReport objects that should be sent out
                the streaming interface.
        """

        reports = self.generator()
        return reports
