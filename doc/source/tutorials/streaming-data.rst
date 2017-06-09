Understanding IOTile Reports
----------------------------

All data from IOTile devices comes in the form of **Reports**.  As the name
suggests, a Report just contains a list of data that the IOTile Device wants
to report to the cloud.  This data is packed into a specific structure for
transportation to the cloud and then unpacked and inspected to make sure it
arrived correctly and originated from the IOTile Device that it claimed to
come from.

In this tutorial, we're going to build our own reports in Python to get a
feel for how the process works and the various classes involved.

At the end we'll talk about how you could upload a report to the cloud on
behalf of a device.

Goals
#####

1. Understand how IOTile devices report data and how they package it into
   reports for transmission.

2. Introduce the classes in `iotile-core` that represent data from IOTile
   devices and their API.

3. Understand the distinction between realtime data and signed *Robust Reports*.

Background
##########

Before talking about how CoreTools handles data from IOTile Devices, we need to
cover how IOTile Devices generate data in the first place.

IOTile Devices are designed to produce timeseries of discrete data points.
Think of a soil moisture sensor programmed to record the water content in the
soil every 10 minutes.  It produces a single data stream which is a series of
discrete soil moisture readings (i.e. single numbers) every 10 minutes.

Now think of a more complicated IOTile Device that measures soil moisture
every 10 minutes but also measures the temperature of the air every hour and
wants to report both of those numbers.  Clearly, there needs to be a way to
distinguish these two data streams so that users know which numbers are
temperatures and which are moisture values.

IOTile Devices distinguish different sensor readings by using a 16-bit
**Stream** identifier (a **Stream ID**), where each different Stream corresponds
to a different type of reading.

All of the data entries in a Stream are time, value pairs, i.e a single reading
that occurred at a specific time.  Most IOTile Devices timestamp their data with
1 second precision.  Currently, each data value saved in a Stream must fit in
32 bits, so it can either be an integer or encoded/packed into an integer.

For example, realtime water flow measurements might report their results as 2
16 bit numbers packed together with one number representing the fractional
part of the flow and the other number representing the whole number part of the
flow (a 16.16 fixed point format).

To save space on small embedded microcontrollers, there are no explicit units
included in data sent from IOTile Devices.

.. important::
    it us up to the user to make sure that they understand the implicit
    units of the data being sent from an IOTile Device, since just bare
    numbers are transmitted from the devices.  The data in each Stream
    must all have the same units.

Since many IOTile devices are not directly connected to the internet, they
typically save up data to transmit periodically to the cloud in the form of a
**Report**.  A Report is simply a data packet with 1 or more readings in it
and some associated header and footer information identifying where it came
from and what it contains.  Reports may be encrypted or cryptographically
signed if desired to provide data privacy and verification of origin.

Key Concepts
############

Reading
    An individual time/value data entry recorded by an IOTile Device. Each
    reading is timestamped and the reading value must fit in 4 bytes (32 bits).
    Every reading must be associated with exactly 1 Stream.

Stream
    A time series of Readings that all have the same units and should be
    logically grouped together.  Usually Streams come from a single sensor.

Stream ID
    A 16-bit number that identifies a stream.  Stream IDs are stored with each
    Reading so that the device can remember what Stream that Reading is
    contained in.

Report
    A Report is a data packet containing one or more Readings from one or more
    Streams that is packaged together for transmission from an IOTile Device to
    a remote user, usually either a mobile phone or the cloud.

    There are different report formats that can be used depending on the
    communication channel constraints and the user's desired privacy and
    security levels for the data.

How CoreTools Handles Reports
#############################

Once data is received from an IOTile Device, it is decoded into an
`IOTileReport` subclass.  All reports processed through CoreTools are
represented as subclasses of `IOTileReport`.

Each IOTileReport contains one or more IOTileReadings which are the way that
CoreTools represents Readings coming from an IOTile Device.

The `IOTileReading` class is pretty simple.

.. py:module:: iotile.core.hw.reports

.. autoclass:: IOTileReading
    :members:

There are two major Report Formats that we are going to be using in this
tutorial.  The first is the `IndividualReportFormat`.  Individual reports
contain a single reading and are used by IOTile devices to communicate
real time data to a connected user that should be stored persistently in the
cloud.

.. important::
    Readings sent in Individual reports cannot be stored persistently in
    iotile.cloud since they do not contain the required unique reading
    identifiers to allow the cloud to deduplicate readings received from
    multiple sources.  **They are only used for transmitting ephemeral,
    realtime data.**

The second major report format is the `SignedListReport`.  Signed list reports,
as the name suggests contain a list of readings, possibly from multiple streams
and can be cryptographically signed to ensure that they came from the device
they claim to come from.

Simulating Realtime Data
########################

.. note::
    This section builds on the virtual device concepts we used in the first
    tutorial on Creating Your First IOTile Device.  If you want an explanation
    for those concepts you should do that tutorial before continuing.

We're going to create a simple virtual IOTile Device that streams realtime
data "temperature" every second.  The data will just be a random number
between 32 and 100.

Just like in the first tutorial, create a class for the virtual device::

    """Virtual IOTile device for CoreTools Walkthrough."""

    import random
    from iotile.core.hw.virtual.virtualdevice import VirtualIOTileDevice


    class DemoVirtualDevice(VirtualIOTileDevice):
        """A simple virtual IOTile device that streams fake temperature.

        Args:
            args (dict): Any arguments that you want to pass to create this
                device.
        """

        def __init__(self, args):
            super(DemoVirtualDevice, self).__init__(1, 'Demo02')

            # Create a worker that streams our realtime data every second
            self.create_worker(self._stream_temp, 1.0)

        def _stream_temp(self):
            """Send a fake temperature reading between 32 and 100."""

            self.stream_realtime(0x1000, random.randint(32, 100))

Save your device file as `demo_streamer.py`.

This time we'll scan for the device before connecting to it. Scanning in real life will display all of the devices you are able to connect to, as well as the unique id (uuid) of each device. You can then connect to it using the
iotile tool *connect*::

    (iotile-virtualenv) > iotile hw --port=virtual:./demo_streamer.py
    (HardwareManager) scan
	{
	    "connection_string": "1",
	    "expiration_time": "2017-05-26 13:06:54.800662",
	    "signal_strength": 100,
	    "uuid": 1
	}
    (HardwareManager) connect 1
    (HardwareManager) enable_streaming
    (HardwareManager) count_reports
    1
    (HardwareManager) count_reports
    2
    (HardwareManager) count_reports
    3
    (HardwareManager) quit

Notice how we used the `enable_streaming` function to inform the IOTile Device
that we wanted to receive reports from it.  Then we used the `count_reports`
function to count how many reports we had received.  It should increase by one
every second when a new reading comes in.

.. note::
    There is not currently a good way to view the contents of the reports in
    the iotile shell tool.  To see what the reports contain, we need to write
    a python script that looks at the IOTileReport objects directly.

Now, let's write a python script that prints out the realtime data as it comes
in::

    from iotile.core.hw.hwmanager import HardwareManager
    from iotile.core.hw.reports import IndividualReadingReport, IOTileReading

    with HardwareManager(port='virtual:./demo_streamer.py') as hw:
        hw.connect('1')
        hw.enable_streaming()

        # hw.iter_reports() will run forever until we kill the program
        # with a control-c so make sure to catch that and cleanly exit
        # without printing an exception stacktrace.
        try:
            for report in hw.iter_reports(blocking=True):

                # Verify that the device is sending realtime data as we expect
                assert isinstance(report, IndividualReadingReport)
                assert len(report.visible_readings) == 1

                reading = report.visible_readings[0]
                assert isinstance(reading, IOTileReading)

                print("Received {}".format(reading))
        except KeyboardInterrupt:
            pass

This script uses the `hw.iter_reports()` function to wait forever for each new
report to come and the let you print it out.  Run it inside your virtual
environment to see it print out all of the readings your device is sending.

Save it as `test_script.py` and then run it to make sure everything works as
expected.

You should see a new reading come once per second.  You can quit the program
by sending it a Ctrl-C event::

    (iotile-virtualenv) > python ./test_script.py
    Received Stream 4096: 34 at 2017-05-17 16:31:46.461000
    Received Stream 4096: 49 at 2017-05-17 16:31:47.522000
    Received Stream 4096: 73 at 2017-05-17 16:31:48.581000
    Received Stream 4096: 55 at 2017-05-17 16:31:49.646000
    Received Stream 4096: 72 at 2017-05-17 16:31:50.706000
    Received Stream 4096: 59 at 2017-05-17 16:31:51.763000
    Received Stream 4096: 36 at 2017-05-17 16:31:52.824000

Reference Information
#####################

We introduced two new functions on `HardwareManager` in this tutorial:
`iter_reports` and `enable_streaming`.  For reference, their API documentation
is here.

.. py:module:: iotile.core.hw.hwmanager

.. autoclass:: HardwareManager
    :members: iter_reports, enable_streaming

Next Steps
##########

This concludes the tutorial on understanding data from IOTile Devices.  We
looked mainly at how realtime data is streamed from IOTile devices and covered
the different report formats that exist inside CoreTools.

Future tutorials will cover creating signed reports that could be uploaded to
iotile.cloud.  That process is a little more involved because the cloud requires
readings that come from devices to include unique identifier information to
ensure data integrity.
