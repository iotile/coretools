Serving Access to Virtual Devices
---------------------------------

Up till now, we have focused on understanding RPCs and realtime data streaming
from IOTile devices.  We've used python classes as virtual devices and
interacted with them directly on your computer.

However, virtual devices are much more powerful than just tutorial usage.  One
of the key foundations of IOTile and CoreTools is that every part of an IOTile
system should be testable and mockable without complicated tools.

For example, let's say you're building a solution for monitoring water meters.
You have an IOTile device attached to the water meter that counts how much
water has passed through the meter and provides access to that data over
Bluetooth.  You also have a mobile app that connects to the water meter and
allows you to download that data and see the flow rate through the pipe in
realtime when you're connected.

It can be challenging to properly test your mobile app across a range of
conditions because you need to trick the water meter into showing you a wide
range of 'fake' flow rates and historical readings on demand.

For a large piece of industrial equipment, it's not always clear how to 'trick'
it into giving you the data you need to test other parts of the system and while
it's easy to generate fake data on a computer, it's not clear how to get your
computer to serve that data over Bluetooth in the same way the water meter would
so you can properly test your mobile app.

Virtual devices fix this problem.  Any IOTile device (including its wireless
connectivity) can be replaced with a Virtual Device that exactly mimics it (
or whatever portion of it we need to test).

So, we can create a simple Virtual Device to act as a stand in for the
real IOTile Device and then have our computer serve it over Bluetooth for the
mobile app to talk to.  Since the Virtual Device will be running on our computer
we'll be able to make it generate whatever data we need for testing.

Goals
#####

1. Understand key CoreTools concepts of Device Adapters and Virtual Interfaces
   and how to use them to mock IOTile Devices for testing.

2. Introduce the **virtual_device** script that serves a Virtual Device over
   a Virtual Interface so that users can connect to it without running
   CoreTools.

3. Show how we can interact with our Virtual Device over Bluetooth from
   CoreTools.

Background
##########

For past tutorials, we've been using VirtualDevices just as a simple tool to
illustrate some of the concepts in IOTile Device interactions like RPCs and
streaming data without needing physical hardware.  To keep things simple,
we directly embedded the virtual device inside of a `HardwareManager` object.

However, that's not the only way that a VirtualDevice can be used.  In a more
general sense, `HardwareManager` loads plugins called `DeviceAdapters` that
tell is how to find and communicate with IOTile Devices.  In past tutorials,
we've implicitly been using a `VirtualDeviceAdapter` plugin that lets
HardwareManager talk directly to a VirtualDevice object running in the same
process as the HardwareManager.

Another way to use a VirtualDevice is to attach it to a `VirtualInterface` that
exposes its RPCs and Streaming interface directly over a communication channel
like Bluetooth Low Energy.

In that case the VirtualDevice ceases to be just a tutorial aid and becomes
basically a normal IOTile Device that just happens to be written in Python
rather than embedded C.

The overall picture then looks like the figure below.

.. figure:: virtual_interface_layers.png
    :width: 30%
    :alt: Stack diagram showing virtual Interfaces

    The stack that allows interacting with a Virtual IOTile Device from another
    computer as if it's a real IOTile device over a communication channel like
    Bluetooth Low Energy.

Users rarely need to interact directly with a VirtualInterface object. Just
as HardwareManager finds DeviceAdapters as needed and loads them by name, there
is a script included with `iotile-core` called **virtual_device** that will take
a VirtualDevice and provide access to it over a VirtualInterface.

Key Concepts
############

DeviceAdapter
    A class whose job is to translate the abstract internal CoreTools
    representations of RPCs, Reports and Readings into concrete packets that
    can be sent to an IOTile Device connected via some communication mechanism.
    For example, the way an RPC is represented over the air will be different
    for a Bluetooth Low Energy connection than it would be for an HTTPS
    connection between the user and the IOTile Device.  Device Adapters provide
    the translation layer between internal CoreTools objects and whatever needs
    to be sent/received over a communication channel.  There needs to be one
    DeviceAdapter for each different communication mechanism that CoreTools
    supports.

VirtualInterface
    VirtualInterfaces are python implementations of the communication stack
    inside an IOTile Device that allows it to communicate with CoreTools.
    For example, a Bluetooth Low Energy VirtualInterface would allow a
    Virtual Device to receive RPCs over Bluetooth LE using the Bluetooth stack
    built-in to your computer.  The combination of a VirtualDevice and a
    VirtualInterface is a complete 'software implementation' of an IOTile
    Device.

virtual_device
    A script included with the `iotile-core` package that loads in
    a VirtualDevice and VirtualInterface by name and then hosts the soft IOTile
    Device.  This script simplifies the process of using VirtualInterfaces.

Using virtual_device
####################

The `virtual_device` script is just a small program whose job is to let you
run a VirtualDevice inside of a VirtualInterface without having to write custom
python code.

VirtualInterfaces and VirtualDevices can be installed in your virtual environment
by packages during the pip install process, and you can use virtual_device to
list what installed interfaces and devices are available using the -l flag::

    (iotile) > virtual_device -l
    Installed Virtual Interfaces:
    - awsiot
    - bled112

    Installed Virtual Devices:
    - simple
    - report_test
    - realtime_test
    - tracing_test
    - no_app

In this case, we had the ability to serve virtual devices over AWS IOT's MQTT
broker and locally over bluetooth using a BLED112 USB->BLE dongle.  There were
5 built-in virtual devices that we had available to us as well.

In this tutorial we'll be using the `realtime_test` device that can be
configured to produce realtime streaming data on demand.

Let's see what the realtime_test device does.

.. py:module:: iotile.mock.devices

.. autoclass:: RealtimeTestDevice

Basically, this is just a configurable device that can simulate realtime
streaming data.  Note that it takes a dictionary of parameters names `args`.
When using the `virtual_device` script, you can set these parameters by passing
a json config file using a `--config` flag on the command line.

.. warning::
    For this next test to work, you will need two BLED112 USB Bluetooth dongles
    attached to your computer to allow for a loopback test and you will need to
    know either their device file on Mac OS and Linux or their COM port number
    on Windows.

In Linux, you will need to find the dongle existing in the /dev directory. You will also need to yourself to the sudo user group with `sudo usermod -a -G dialout [username]`.

First, create a config file named `device_config.json`::

    {
        "interface":
        {
            "port": "<path to device file or port, dongle 1>"
        },

        "device":
        {
            "iotile_id": "0x10",
            "streams":
            {
                "0x1000": [1.0, 50],
                "0x2000": [0.5, 100]
            }
        }
    }

Now, start running your virtual device using::

    (iotile) > virtual_device bled112 realtime_test --config device_config.json
    Starting to serve virtual IOTile device

.. note::
    If there was an error finding the VirtualDevice realtime_test, make sure
    you have a recent version of iotile-test installed using::

        pip install --upgrade iotile-test

.. note::
    To run a virtual device that hasn't been installed, simply replace the 
    installed device name with the path to your virtual device. For example,
    to run our "demo_streamer" device you might use::

        (iotile) > virtual_device bled112 ./demo_streamer.py

Now your computer is advertising itself as an IOTile Device over bluetooth.
Either using a second computer or using a different terminal on the same
computer, we're going to connect to the device over bluetooth::

    (iotile) > iotile hw --port=bled112:<path to second dongle>
    (HardwareManager) scan
    {
        "connection_string": "88:6B:0F:18:34:AF",
        "expiration_time": "2017-05-18 10:36:23.491000",
        "low_voltage": false,
        "pending_data": false,
        "signal_strength": -39,
        "user_connected": false,
        "uuid": 16
    }

Note how we used the port string bled112 to indicate that we wanted to
connect to the device over bluetooth.  In previous tutorials, we've used the
virtual DeviceAdapter rather than Bluetooth Low Energy.  Make sure you pass
the correct COM port or file path in the port string otherwise you will get an
error.

Now when we type scan, the results we get will be bluetooth based IOTile Devices
that are in range of our computer.  Here we see the virtual device that we just
set up with UUID 0x10 (decimal 16).  We see an RSSI signal strength of -39 dBm
and see that no one is currently connected to it.

So, let's connect and see the realtime streaming data come in over Bluetooth::

    (HardwareManager) connect 0x10
    (HardwareManager) enable_streaming

Now look back at the virtual device terminal and you'll see it log audit
messages telling you in detail what it's doing::

    Starting to serve virtual IOTile device
    2017-05-18 10:42:40,453 [AUDIT ClientConnected] A client connected to this device
    2017-05-18 10:42:40,865 [AUDIT RPCInterfaceOpened] A client opened the RPC interface on this device
    2017-05-18 10:42:44,888 [AUDIT StreamingInterfaceOpened] A client opened the streaming interface on this device
    2017-05-18 10:42:45,163 [AUDIT ReportStreamed] The device streamed a report to the client, report=IOTile Report of length 20 with 1 visible readings
    2017-05-18 10:42:45,572 [AUDIT ReportStreamed] The device streamed a report to the client, report=IOTile Report of length 20 with 1 visible readings
    2017-05-18 10:42:45,680 [AUDIT ReportStreamed] The device streamed a report to the client, report=IOTile Report of length 20 with 1 visible readings
    2017-05-18 10:42:46,191 [AUDIT ReportStreamed] The device streamed a report to the client, report=IOTile Report of length 20 with 1 visible readings
    2017-05-18 10:42:46,698 [AUDIT ReportStreamed] The device streamed a report to the client, report=IOTile Report of length 20 with 1 visible readings
    2017-05-18 10:42:46,707 [AUDIT ReportStreamed] The device streamed a report to the client, report=IOTile Report of length 20 with 1 visible readings
    2017-05-18 10:42:47,315 [AUDIT ReportStreamed] The device streamed a report to the client, report=IOTile Report of length 20 with 1 visible readings
    2017-05-18 10:42:47,724 [AUDIT ReportStreamed] The device streamed a report to the client, report=IOTile Report of length 20 with 1 visible readings
    2017-05-18 10:42:47,829 [AUDIT ReportStreamed] The device streamed a report to the client, report=IOTile Report of length 20 with 1 visible readings
    2017-05-18 10:42:48,338 [AUDIT ReportStreamed] The device streamed a report to the client, report=IOTile Report of length 20 with 1 visible readings
    2017-05-18 10:42:48,848 [AUDIT ReportStreamed] The device streamed a report to the client, report=IOTile Report of length 20 with 1 visible readings
    2017-05-18 10:42:48,954 [AUDIT ReportStreamed] The device streamed a report to the client, report=IOTile Report of length 20 with 1 visible readings
    2017-05-18 10:42:49,309 [AUDIT StreamingInterfaceClosed] A client closed the streaming interface on this device
    2017-05-18 10:42:49,311 [AUDIT ClientDisconnected] A client disconnected from this device

These audit messages are a great way to see in detail what's going on from the
IOTile device's standpoint if you're trying to debug another part of the stack.

Now let's see how RPCs look when sent over Bluetooth.  Stop the virtual_device
by sending it a Ctrl-C signal and then create a new one using the `simple`
device that supports RPCs::

    (iotile) > virtual_device bled112 simple --config device_config.json
    Starting to serve virtual IOTile device

This device has a fixed UUID of 1, so let's connect to it::

    (iotile) > iotile hw --port=bled112:<path to second bled dongle
    (HardwareManager) connect 1
    (HardwareManager) controller
    (SimpleProxy) tile_status
    configured: True
    debug_mode: False
    app_running: True
    trapped: False

The SimplyProxy is built-in to `iotile-test` for testing and demo purposes.

Let's see what the RPCs look like over bluetooth now::

    2017-05-18 10:53:48,516 [AUDIT ClientConnected] A client connected to this device
    2017-05-18 10:53:48,854 [AUDIT RPCInterfaceOpened] A client opened the RPC interface on this device
    2017-05-18 10:53:59,391 [AUDIT RPCReceived] An RPC has been processed (id=4, address=8, payload=""), status=192, response="ffff53696d706c6501000003"
    2017-05-18 10:53:59,440 [AUDIT RPCReceived] An RPC has been processed (id=4, address=8, payload=""), status=192, response="ffff53696d706c6501000003"
    2017-05-18 10:54:03,661 [AUDIT RPCReceived] An RPC has been processed (id=4, address=8, payload=""), status=192, response="ffff53696d706c6501000003"

Here we see the RPC as received by the virtual device from the bluetooth stack
and the raw hex bytes sent back in response.  Note that when we called
`controller` on the HardwareManager instance it sent two RPCs on our behalf to
ask the virtual device for its 6-byte identifier that it uses to match it to a
Proxy object.  That's how it knew that it should load the SimpleProxy object.

The tile_status command is supported by every IOTile Device (and even by each
individual tile inside composite devices) and just shows basic status
information about whether there are any issues with the device.  In this case
everything's running fine.

Scripting Actual Devices
########################

One of the core principles of IOTile is orthogonality, which means that a given
script or command should be able to be used no matter what the IOTile Device is
and no matter how its connected to the user.  In this case, we're going to reuse
the exact same script we used before to print realtime streaming data from our
virtual device to now print the realtime data coming from our actual (soft)
device over bluetooth.

Start the realtime_test device again::

    (iotile) > virtual_device bled112 realtime_test --config device_config.json
    Starting to serve virtual IOTile device

Now load up your realtime stream dumping script from the last tutorial (fixing
the port to use bled112 instead of virtual (test_script.py)::

    from iotile.core.hw.hwmanager import HardwareManager
    from iotile.core.hw.reports import IndividualReadingReport, IOTileReading

    with HardwareManager(port='bled112:<path to dongle or COM port>') as hw:
        hw.connect(0x10)
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

Run it and see the realtime data coming from your device::

    (iotile) > python ./test_script.py
    Received Stream 4096: 50 at 2017-05-18 18:05:45.693000
    Received Stream 8192: 100 at 2017-05-18 18:05:45.693000
    Received Stream 8192: 100 at 2017-05-18 18:05:46.211000
    Received Stream 4096: 50 at 2017-05-18 18:05:46.727000
    Received Stream 8192: 100 at 2017-05-18 18:05:46.727000
    Received Stream 8192: 100 at 2017-05-18 18:05:47.337000
    Received Stream 4096: 50 at 2017-05-18 18:05:47.842000
    Received Stream 8192: 100 at 2017-05-18 18:05:47.852000
    Received Stream 8192: 100 at 2017-05-18 18:05:48.350000
    Received Stream 4096: 50 at 2017-05-18 18:05:48.859000
    Received Stream 8192: 100 at 2017-05-18 18:05:48.859000
    Received Stream 8192: 100 at 2017-05-18 18:05:49.468000

If you have a physical IOTile device as well, you could now point your
script at it and have it show you the realtime sensor data coming from the
device.

Next Steps
##########

After finishing this tutorial, you're ready to build your own virtual IOTile
Device and allow access to it over bluetooth.
