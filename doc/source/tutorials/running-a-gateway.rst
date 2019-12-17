Setting Up a Gateway
--------------------
You may have to `pip install iotile-gateway`.

Many times individual IOTile Devices are not able to directly connect to the
internet and instead talk exclusively to an intermediate gateway device.  This
is usually because the devices lack the required communications hardware to
send multi-hop or IP routed transmissions.  An example would be a battery
powered wireless sensor connected via Bluetooth Low Energy.  BLE devices
connect to a local central device in a point-to-point fashion without a built-in
provision for connecting to the internet.

So, there's often a need for a gateway that knows how to connect to a specific
sensor device and then serves access to that device over a different protocol,
acting as a translator between, e.g. BLE and Websockets, or BLE and MQTT.

Since all IOTile Devices implement the same basic interfaces for streaming
data and receiving RPC commands, we can make a generic gateway program that
translates requests from any supported protocol into any other supported
protocol.

This program, and the python objects behind it, is called `iotile-gateway` and
is provided by the iotile-gateway package in CoreTools.

Goals
#####

1. Understand how to configure iotile-gateway to translate between communication
   protocols.
2. Use iotile-gateway to aggregate devices across multiple communication
   protocols by plugging multiple DeviceAdapters into the same gateway.
3. Understand the use case for mixing physical and virtual IOTile devices in the
   same gateway to allow for remote configuration of the gateway computer as
   well as providing access to other IOTile Devices.

Background
##########

In previous tutorials, we've seen how DeviceAdapters provide a generic way to
allow access to IOTile devices from multiple clients and how HardwareManager
allows a single client or script to discover and make a connection to a specific
IOTile Device.

We've also seen how we can create our own device and serve access to it using
a VirtualInterface.  In this tutorial we're going to introduce
**GatewayAgents**.

GatewayAgents are the direct complement to DeviceAdapters.  Whereas
DeviceAdapters standardize devices that may have very different communication
protocols, GatewayAgents take those standardize devices and re-broadcast them
over a different communucation protocol.  So, you could take a device connected
over Bluetooth and serve it up over Websockets, MQTT, or HTTPS.

Since there are many moving pieces in performing this kind of translation, there
needs to be a host application that provides the framework for linking
DeviceAdapters and GatewayAgents together.  This program is called
**iotile-gateway** and is installed as a script when you `pip install` the
iotile-gateway package in CoreTools.

The heavy lifting is done by an asynchronous event loop managed by the
**AggregatingDeviceAdapter** class.

.. py:module:: iotilegateway.device

.. autoclass:: AggregatingDeviceAdapter
    :noindex:

By itself, AggregatingDeviceAdapter does not allow serving access to IOTile Devices, it
just aggregates multiple DeviceAdapters together and unifies the view of the
devices that they can see.

There still needs to be a way to configure what DeviceAdapters to add to the
AggregatingDeviceAdapter and to specify what GatewayAgents should be included as well.

This is performed by the **IOTileGateway** class.  IOTileGateway is designed
for simple integration into host applications and forms the backbone of the
iotile-gateway command line program.

.. py:module:: iotilegateway.gateway

.. autoclass:: IOTileGateway
    :noindex:

The overall structure of the iotile-gateway system is shown in the figure below.
You can see the different device adapters that can be used to find IOTile
Devices and the various gateway agents that allow users to access them.

.. figure:: iotile_gateway.png
    :width: 30%
    :alt: Stack diagram of iotile-gateway

    The structure of the iotile-gateway program that translates between
    different communication protocols to allow remote control of IOTile Devices
    that don't possess long-range communications hardware.

Key Concepts
############

    A class that takes multiple DeviceAdapters and merges all of the devices
    that they can see.  Requests to connect to individual devices are routed to
    the appropriate DeviceAdapter based on which adapters can see that device,
    what their signal strength is and whether they have the resources for an
    additional connection.

IOTileGateway
    A helper class that locates and loads DeviceAdapter and GatewayAgent plugins
    and then runs a DeviceManager instance with those plugins in a separate
    thread to allow for easy integration into a host application

GatewayAgent
    A class that serves access to IOTile Devices over a communication protocol.
    This class serves the opposite function as a DeviceAdapter and you would
    imagine a natural pairing where each DeviceAdapter has a corresponding
    GatewayAgent.

iotile-gateway
    A cross-platform command line script that allows turning a computer into a
    turn-key gateway that searches for IOTile Devices using DeviceAdapters and
    then serves access to them using GatewayAgents.  A JSON configuration file
    lets you specify what plugins to load and how to configure them

Using iotile-gateway
####################

The iotile-gateway program is fairly turn-key.  You just need to tell it what
DeviceAdapters to load and what GatewayAgents to use.  The DeviceAdapters are
configured by passing the same 'port' string you would use in the iotile tool.

The GatewayAgents have more configurability and take a dictionary of arguments
that are specific to each agent. In this example, we're going to use our
venerable VirtualDeviceAdapter to connect to a virtual device and serve access
to it over Websockets.

Websockets are a bidirectional communication channel built on top of http that
is widely used in javascript web applications, so serving IOTile Devices over
web sockets is a great way to connect them to web apps.

We'll need to create a config file with the required information (named
gateway.json)::

    {
        "agents":
        [
            {
                "name": "websockets",
                "args":
                {
                    "port": 5120
                }
            }
        ],

        "adapters":
        [
            {
                "name": "virtual",
                "port": "realtime_test"
            }
        ]
    }

Then we just run iotile-gateway and point it to our config file::

    (iotile) > iotile-gateway --config=gateway.json
    I-2017-05-19 14:38:18,977-gateway   :94   Loading agent by name 'websockets'
    I-2017-05-19 14:38:19,381-ws_agent  :38   Starting Websocket Agent on port 5120
    I-2017-05-19 14:38:19,388-gateway   :116  Loading device adapter by name 'virtual' and port 'realtime_test'

Now (in another shell or a separate computer on the same network),
we can connect to the gateway just like we connect directly to an IOTile
Device by specifying a protocol supported by one of the gateway's agents, in
this case websockets::

    (iotile) > iotile hw --port=ws:localhost:5120/iotile/v1
    (HardwareManager) scan
    {
        "adapters": [
            [
                0,
                100,
                "0/1"
            ]
        ],
        "best_adapter": 0,
        "expires": "2017-05-26 13:23:46.277000",
        "signal_strength": 100,
        "uuid": 1
    }

Note how there is a little more detail here than when you scan directly from
the IOTile tool.  In particular we see a list of all of the DeviceAdapters that
could see the device ranked in order of signal strength and a key specifying
the best adapter to use to connect to the device.

If this were, for example, a Bluetooth device and we had two different Bluetooth
adapters connected to the computer, we would see the device twice but they
would both be merged into a single entry with the closest adapter used to
actually make the connection.

Combining Multiple Device Adapters
##################################

There is no restriction on the number of different device adapters that you
can connect to a gateway, so let's use two virtual adapters::

    {
        "agents":
        [
            {
                "name": "websockets",
                "args":
                {
                    "port": 5120
                }
            }
        ],

        "adapters":
        [
            {
                "name": "virtual",
                "port": "realtime_test"
            },

            {
                "name": "bled112"
            }
        ]
    }

.. important::

    You need a BLED112 USB bluetooth dongle plugged into your computer for
    this to work.

In this case, we're going to find physical IOTile Devices over bluetooth as
well as our virtual device.  This combination of physical and virtual devices
is often very useful since virtual devices can provide you a way to configure
things on the computer running the gateway program.

For example, lets say you're deploying a gateway on a remote farm that you
are going to use to control a variety of bluetooth sensors.  It would be great
if you could also control the gateway computer itself.  By making a virtual
device that allows control of the gateway and connecting it to the
iotile-gateway as well as the bluetooth adapter, you're able to introspectively
access the gateway just as easily as you can reach through it to access a
local bluetooth device::

    (iotile) > iotile hw --port=ws:localhost:5120/iotile/v1
    (HardwareManager) scan
    {
        "adapters": [
            [
                0,
                100,
                "0/1"
            ]
        ],
        "best_adapter": 0,
        "expires": "2017-05-26 13:39:15.516000",
        "signal_strength": 100,
        "uuid": 1
    }
    {
        "adapters": [
            [
                1,
                -79,
                "1/C0:05:C8:DB:E5:45"
            ]
        ],
        "best_adapter": 1,
        "expires": "2017-05-19 15:00:16.032000",
        "low_voltage": false,
        "pending_data": true,
        "signal_strength": -79,
        "user_connected": false,
        "uuid": 53
    }
    {
        "adapters": [
            [
                1,
                -66,
                "1/D0:45:A7:7E:A9:F0"
            ]
        ],
        "best_adapter": 1,
        "expires": "2017-05-19 15:00:16.283000",
        "low_voltage": false,
        "pending_data": false,
        "signal_strength": -66,
        "user_connected": true,
        "uuid": 54
    }

Here we see a number of devices that our gateway found over bluetooth as well
as our virtual device.  You can connect to any device by uuid in the same manner
so you don't have to worry about which devices are physical vs virtual.

Next Steps
##########

After this tutorial you should be ready to set up your own IOTile Gateway that
translates devices from one communication protocol to another.  You should also
be able to use what you learned in the previous tutorials to add virtual devices
to your gateway that let you control things directly connected to the gateway
computer or configure the gateway itself as if it were an IOTile Adapter.

You can read on to figure out how to configure your own physical IOTile devices
using the SensorGraph language.
