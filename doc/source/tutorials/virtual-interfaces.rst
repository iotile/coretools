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
it into giving you the data you need to test other parts of the sytem and while
it's easy to generate fake data on a computer, it's not clear how to get your 
computer to serve that data over Bluetooth in the same way the water meter would
so you can properly test your mobile app.

Virtual devices fix this problem.  Any IOTile device (including its wireless
connectivity) can be replaced with a Virtual Device that exactly mimicks it (
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
   CoreTools and from the IOTile Companion mobile app.

.. important::
    In order to do the later parts of the tutorial, you will need to have an
    IOTile.cloud account and at least one physical IOTile Device so that the
    Companion app has the right metadata to connect to your virtual stand-in
    device.

Background
##########

For past tutorials, we've been using VirtualDevices just as a simple tool to 
illustrate some of the concepts in IOTile Device interactions like RPCs and 
streaming data without needing physical hardware.  To keep things simple,
we directly embedded the virtual device inside of a `HardwareManager` object.  

However, that's not the only way that a VirtualDevice can be used.  In a more
general sense, `HardwareManager` loads plugins called `DeviceAdapters` that
tell is how to find and communicate with IOTile Devices.  In past tutorials,
we've implictly been using a `VirtualDeviceAdapter` plugin that lets
HardwareManager talk directly to a VirtualDevice object runing in the same
process as the HardwareManager.

Another way to use a VirtualDevice is to attach it to a `VirtualInterface` that
exposes its RPCs and Streaming interface directly over a communication channel
like Bluetooth Low Energy.  

In that case the VirtualDevice ceases to be just a tutorial aid and becomes
basically a normal IOTile Device that just happens to be written in Python
rather than embedded C.

The overall picture then looks like the figure below.

.. figure:: virtual_interface_layers.png
    :width: 50%
    :alt: Stack diagram showing virtual Interfaces

    The stack that allows interacting with a Virtual IOTile Device from another
    computer as if it's a real IOTile device over a communication channel like
    Bluetooth Low Energy.

