"""Reference device for testing the individual report format
"""

from iotile.core.hw.virtual.virtualdevice import VirtualIOTileDevice, rpc, RPCInvalidIDError, RPCNotFoundError, TileNotFoundError
from iotile.core.exceptions import ArgumentError
from iotile.core.hw.reports import IndividualReadingReport, IOTileReading, SignedListReport

class ReportTestDevice(VirtualIOTileDevice):
    """Mock IOTileDevice that creates a sequence of reports upon connection

    This device can be considered a reference implementation of the individual
    reading and signed list report formats.

    Args:
        args (dict): Any arguments that you want to pass to create this device.
            Supported args are:
                iotile_id (int): The UUID used for this device (default: 1)
                num_readings (int): The number of readings to be generated every
                    time the streaming interface is opened. (default: 100)
                starting_timestamp (int): The first timestamp that should be generated
                    for the first Reading sent.  Timestamps are sequential for each
                    reading, so x, x+1, etc.
                    Default: 0
                starting_id (int): The first reading id that should be generated
                    for the first Reading sent.  Reading IDs will be sequential after
                    starting_id so x, x+1, x+2.
                    Default: 1
                reading_generator (string): The method for generating readings. 
                    Options are: sequential, random (default: sequential)
                    random will generate random values between the reading_min and
                    reading_max keys (default: 0, 100)
                    sequential will sequentially generate reading values starting
                    at reading_start (default: 0)
                format (string): The report format to package in (either individual
                or signed_list).  (default: individual)
                report_length (int): The maximum number of readings per report
                    (default: 10).  The only applies to report formats that can contain
                    multiple readings
                signing_method (int): The signature type to be applied to signed messages
                    Common values would be 0 for a hash only signature with no origin 
                    verification functionality or 1 for signing with a user set key.  
                    (default: 0)
    """

    def __init__(self, args):
        iotile_id = args.get('iotile_id', 1)

        if isinstance(iotile_id, basestring) or isinstance(iotile_id, unicode):
            iotile_id = int(iotile_id, 16)

        generator = args.get('reading_generator', 'sequential')            
        self.num_readings = args.get('num_readings', 100)

        stream_string = args.get('stream_id', '5001')
        self.stream_id = int(stream_string, 16)

        self.signing_method = args.get('signing_method', 0)
        self.start_timestamp = args.get('starting_timestamp', 0)
        self.start_id = args.get('starting_id', 1)
        
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

        self.format = args.get('format', 'individual')
        if self.format not in ['individual', 'signed_list']:
            raise ArgumentError("Unknown report format for generator", format=self.format, known_formats=['individual', 'signed_list'])

        self.report_length = args.get('report_length', 10)

        if self.report_length == 0 and self.format != 'individual' and self.num_readings != 0:
            raise ArgumentError("You cannot have a report length of 0 and more than 0 readings because that would be an infinite loop")

        super(ReportTestDevice, self).__init__(iotile_id, 'Simple')

    @rpc(8, 0x0004, "", "H6sBBBB")
    def controller_name(self):
        """Return the name of the controller as a 6 byte string
        """

        status = (1 << 1) | (1 << 0) #Configured and running
        
        return [0xFFFF, self.name, 1, 0, 0, status]

    def _generate_sequential(self):
        readings = []
        
        for i in xrange(self.reading_start, self.num_readings+self.reading_start):
            reading = IOTileReading(i-self.reading_start+self.start_timestamp, self.stream_id, i, reading_id=i-self.reading_start+self.start_id)
            readings.append(reading)

        return readings

    def _generate_random(self):
        return []

    def open_streaming_interface(self):
        """Called when someone opens a streaming interface to the device

        Returns:
            list: A list of IOTileReport objects that should be sent out
                the streaming interface.
        """

        readings = self.generator()

        reports = []

        if self.format == 'individual':
            reports = [IndividualReadingReport.FromReadings(self.iotile_id, [reading]) for reading in readings]
        elif self.format == 'signed_list':
            if self.report_length == 0:
                return [SignedListReport.FromReadings(self.iotile_id, [], signature_method=self.signing_method)]

            for i in xrange(0, len(readings), self.report_length):
                chunk = readings[i:i+self.report_length]
                report = SignedListReport.FromReadings(self.iotile_id, chunk, signature_method=self.signing_method)
                reports.append(report)

        return reports
