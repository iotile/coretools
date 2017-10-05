Introduction to SensorGraph
---------------------------

Previous tutorials have covered how to create virtual IOTile devices that expose
functionality in terms of RPCs that can be called to, for example, read a sensor
or flip a switch.  We've also seen how we can interact with those devices from
a computer using `CoreTools` to send commands and extract data over a variety
of communications channels.

However, we haven't yet touched on how you could embed a program into one of
these devices so that it can be left running and autonomously collect data
or take actions.

For example, lets say you have a device that can measure the temperature of the
air in the room and you want to configure it to measure that temperature every
10 minutes and if its too hot, turn on the AC.

Basically you want a simple script that does the following::

    every 10 minutes
    {
        measure temperature
    }

    if temperature > upper_limit
    {
        enable AC
    }

In this tutorial we are going to cover how to write these scripts for an IOTile
device in a language called **SensorGraph** that makes it easy to write scripts
and verify that they work as intended before deploying them to a potentially
remote and mission critical location.

Goals
#####

1. Understand what SensorGraph is at a high level and what the major components
   of the sensor graph system are.
2. Be able to write and simulate SensorGraph scripts on your computer using the
   `iotile-sensorgraph` package in `CoreTools`.
3. Understand the major statements and blocks that make up a SensorGraph script.

Background
##########

The way to think of an IOTile device is as a set of APIs, just like a web
service would have a set of REST APIs that you can wire together to make an
application.

Without an Application tying the APIs together the system won't do anything, it
will just sit and wait for someone to call one of its APIs (like we did in
previous tutorials).

Most applications that we want to write on IOTile devices are fairly small and
just wire together a few APIs to collect data and then prepare it for either
remote transmission to the cloud or use it to control some local process.

There are three parts to an IOTile application:

1. **Configuring the device:** An IOTile device is made up of several different
   modules called tiles.  These tiles are designed to be used in a variety of
   different ways, so you may need to configure them to be in the right mode
   of operation for what you want.  Configuration of all tiles happens once
   when the IOTile device turns on.

2. **Wiring tiles together to collect data:** Once the IOTile device is
   configured, there needs to be a script that it runs through that tells it
   what RPCs to call on which tiles in order to collect data or control things.
   This script could either be time driven like 'collect data every 10 minutes'
   or event driven as in 'when this happens to this'.  Combinations of time
   driven and event driven actions are also possible.

3. **Choosing what data to report:** Often times IOTile devices are designed to
   send data they collect to a remote server in the cloud for further processing.
   Usually you only want a subset of the data that an IOTile device generates
   to be sent remotely in order to save bandwidth, power or money.  So, there
   needs to be some rules in place that select what data gets sent remotely.

   The selected data is packaged into **Reports** as described in a previous
   tutorial.  In this section we're talking about how the device knows what
   data should go into those reports and what data is only for internal use.

   The part of the IOTile device that is responsible for choosing data for
   remote transmission is a **Streamer**.  Streamers determine what data is
   sent, under what conditions it is sent, how retries are handled and what
   report format to use (i.e. what level of security and robustness
   guarantees are required).

Normally, the data that an IOTile device generates can be divided into two
classes:

- **Realtime Data:** Realtime data is continually being regenerated and does not
  have any long term value.  It could be, for example, the current temperature
  of a device that is updated once per second.  There is no need to keep more
  than one current temperature reading around.

- **Historical Data:** Other data is specifically designed to be saved in long
  term storage.  For example, consider using that same temperature monitoring
  device to record a profile of the temperature experienced by a package along
  a multi day journey around the world.  You want to keep historical readings
  around because the point is to have a record, not just the latest value.

Because these two types of data are so common, IOTile Devices handle them
separately.  Realtime data is referred to as **unbuffered data** and is never
stored in a persistent memory location like flash memory.  It can change very
rapidly without wearing out any persistent storage medium.

In contrast, historical data is treated as **buffered data** and every value
written to a data stream marked as historical data will be saved securely and
assigned a globally unique identifier so that it can be robustly transferred
to a remote server and acknowledged that it was correctly received.

So, buffered data corresponds to data that should be tracked over time and
unbuffered is for realtime data and intermediate results that will be
overwritten when new data comes in.

Only the user knows what data should be buffered vs unbuffered so part of
designing a SensorGraph is specifying how to treat each data stream that
is generated should be stored.

Key Concepts
############

Tile Configuration
    A series of variable assignments that are performed on an IOTile module in
    order to prepare it for operation.  These configurations can things like
    set what units it reports data in or selecting what sensor is plugged into
    a tile that can work with many different kinds of sensors.

Streamer
    A task running on an IOTile Device whose job is to send some subset of the
    data generated by that device to a remote server in a configurable way.
    Streamers choose what data to send, when to send it, how it is packaged
    and how retries are handled if an initial attempt to send the data fails.

Buffered Data
    Data that is tracked with a unique identifier and stored securely in
    long term storage.  Once buffered data is generated, it will stay around
    until the device is forced to overwrite it due to a lack of space or it
    is successfully transferred to a remote server.

Unbuffered Data
    Data that is ephemeral and not persistently stored.  Whenever a new reading
    comes in, it overwrites that last unbuffered reading in the same data
    stream.

Creating Your First SensorGraph
###############################

With this background information in hand, we're ready to try out our first
complete sensor graph in a simulator so we can see how everything works.

.. important::
    For this tutorial you will need to make sure the `iotile-sensorgraph`
    package is installed::

        pip install -U iotile-sensorgraph

In this tutorial, we're going to write sensors graphs by example without diving
too much into the mechanics behind it.  A later tutorial will go deeper into
how everything works behinds the scenes.

Let's start with a complete simple sensor graph that just calls an RPC every
10 minutes::

    every 10 minutes
    {
        call 0x8000 on slot 1 => output 1;
    }

Basically we're asking the device to call the RPC with id `0x8000` on the tile
located in `slot 1` once every 10 minutes and to store the output in a stream named
`output 1`.  Save this file as **simple.sgf** and then you can simulate it
in the sensor graph simulator named `iotile-sgrun` that is installed by the
`iotile-sensorgraph` package::

    (iotile) > iotile-sgrun simple.sgf -s 'run_time 1 hour' -w 'output 1'
    (     600 s) output 1: 0
    (    1200 s) output 1: 0
    (    1800 s) output 1: 0
    (    2400 s) output 1: 0
    (    3000 s) output 1: 0
    (    3600 s) output 1: 0

In addition to the sensor graph file that we wanted to simulate, we also passed
a **stop condition** (-s 'run_time 1 hour') that stops the simulation after 1 hour
of simulated time has passed.  We also told the simulator to **watch** (-w) the
stream named 'output 1' and report whenever data was written to it.

The output showed us that a 0 was output ever 10 minutes (600 seconds) for a
total of 6 readings in 1 hour.

This is a complete sensor graph that you could program into an iotile device
and have it take data every 10 minutes forever.  It's not that interesting
of a SensorGraph though, so we'll add some more to it later.

Mocking RPCs
############

In our example above, the simulator called the RPC numbered `0x8000` and stored
its result in output 1.  Evidently the RPC returned a 0.

**By default, all simulated RPCs return 0.**

You can override this behavior by specifying an explicit return value using
the `-m` option to the simulation.  Let's say we want to simulate an RPC that
returns 15 rather than 0. We simulate by passing a `-m` option that defines the slot and RPC number to return 15::

    (iotile) > iotile-sgrun simple.sgf -s 'run_time 1 hour' -w 'output 1' -m 'slot 1:0x8000 = 15'
    (     600 s) output 1: 15
    (    1200 s) output 1: 15
    (    1800 s) output 1: 15
    (    2400 s) output 1: 15
    (    3000 s) output 1: 15
    (    3600 s) output 1: 15

.. note::
    There is a more advanced way to use the simulator called 'semihosting'
    where the RPCs are sent to an actual iotile device to run and the response
    is returned to the simulator.  This lets you test your sensor graph as if
    it were running on an actual device while still being able to watch any
    stream and accelerate the passage of simulated time to verify that the
    sensor graph behaves as you would expect over time without having to have
    an actual device running for that long.

    **How to use semihosting will be covered in the next tutorial.**

The syntax for mocking an RPC straightforward::

    -m "<slot id>:<rpc number> = <value>"

    - <slot id> should be either the literal value `controller` or 'slot X'
    where X is a number >= 1.

    - <rpc number> should be the same 16 bit number in either decimal or hex
    that you enter into the sensor graph to identify the RPC you want to call.

    - <value> should be an integer that will simulate what the RPC returned.
    It is not currently possible to change what the mocked RPC returns over
    time from the command line; it always returns the same thing.

    For example:

    - m "controller:0x2000 = 0x50"
    - m "slot 5:1500 = 12"

Adding Control to a SensorGraph
###############################

The first sensor graph above just got data via an RPC and then saved it as
a buffered output.  We used an `every <unit time>` block to specify how often
we wanted the RPC called.  Now we're going to introduce the `on` block that
lets us inspect and act on the values we get.

Let's say our RPC represents temperature and we want to turn on the AC when
the temperature rises above a certain temperature (say 80 degrees).  We can
express that as follows::

    every 10 minutes
    {
        call 0x8000 on slot 1 => unbuffered 1;
    }

    on value(unbuffered 1) > 80
    {
        # In this example, 0x9000 is the RPC that turns on the AC
        call 0x9000 on slot 2;
    }

    on unbuffered 1
    {
        copy => output 2;
    }

This sensor graph will still log the temperature every 10 minutes but also
check if its value is greater than 80 degrees and call another RPC that turns
on the AC.  (Note in a real life example, you would probably want another
on block to turn off the AC as well!)

.. note::

    See how there are two ways to use the `call` statement.  In the first call,
    we specified that we wanted to keep track of the value returned by the RPC
    so we gave it a name.  In the second call, we didn't care about the return
    value of the RPC so we didn't give it an explicit name.

    Internally, the sensor graph compiler automatically allocated an unused
    stream for this value that we'll see in the next tutorial how this turns
    into the actual rules that could be programmed into .

Adding Realtime Data Outputs
############################

Most IOTile devices don't have screens.  However, users can walk up them with
their phones and access their virtual screen over Bluetooth Low Energy.

When a user is standing next to an IOTile device, they probably don't want to
wait 10 minutes to see the next data point, so there needs to be a way to
trigger faster data outputs when a user is connected to the device.

This functionality is built in to sensor graph and can be enabled using a `when`
block as in the example below::

    every 10 minutes
    {
            call 0x8000 on slot 1 => unbuffered 1;
    }

    when connected to controller
    {
        on connect
        {

        }

        every 1 second
        {
            call 0x8000 on slot 1 => unbuffered 10;
            call 0x8001 on slot 1 => unbuffered 11;
        }

        on disconnect
        {

        }
    }

The `when connected to controller` block specifies actions that should
only be taken when a user is connected. 

This sensor graph says that when a user is connected two RPCs should be made
every second and the results stored in unbuffered streams 10 and 11.

The `on connect` and `on disconnect` blocks are not required if they are unused but are included here for reference. The `on connect` and `on disconnect` blocks allow you to do any required setup or cleanup on the device that might be necessary to prepare it for high resolution outputs and then put it back into low power autonomous mode when the user disconnects.

Now let's simulate this for 10 seconds::

    (iotile) > iotile-sgrun simple.sgf -s 'run_time 10 seconds' -w "unbuffered 10" -w "unbuffered 1"
    (iotile) >

We didn't see any output because no user was connected and we didn't wait 10
minutes for a reading.

So let's set the run time to 10 minutes to make sure the readings are happening::

    (iotile) > iotile-sgrun simple.sgf -s 'run_time 10 minutes' -w "unbuffered 10" -w "unbuffered 1"
    (     600 s) unbuffered 1: 0

Now let's simulate a connected user with the `-c` flag::

    (iotile) > iotile-sgrun simple.sgf -s 'run_time 10 seconds' -w "unbuffered 10" -c

    (       1 s) unbuffered 10: 0
    (       2 s) unbuffered 10: 0
    (       3 s) unbuffered 10: 0
    (       4 s) unbuffered 10: 0
    (       5 s) unbuffered 10: 0
    (       6 s) unbuffered 10: 0
    (       7 s) unbuffered 10: 0
    (       8 s) unbuffered 10: 0
    (       9 s) unbuffered 10: 0
    (      10 s) unbuffered 10: 0

Notice how we now got realtime outputs now in the stream `[unbuffered 10]` every
second.

Selecting Data to Stream
########################

In the beginning of this tutorial, we laid out three jobs for a SensorGraph:

1. Configuring tiles
2. Wiring together RPCS into an application
3. Selecting data to send remotely

We've focused on step 2 so far.  Step 1 will be addressed in the next tutorial
so we will briefly touch on step 3 now.

As mentioned, the way to send data from an IOTile Device is referred to as
**Streaming** and is done by a **Streamer**.

When you write a sensor graph you need to explicitly say what streamers you want
to set up so that the device can be configured properly.  Just like there are
two kinds of data produced by an IOTile device, there are also two kinds of
streamers: realtime and historical.

Realtime streamers report the latest value in a stream without worrying about
robustness packaging it or retrying the transmission if its not successful
because it's expected that they can just send an updated value when its
available.

Historical (or Robust) streamers take much more care in signing and optionally
encrypting the data before sending it and keeping track of exactly which readings
have been acknowledged as successful received by the cloud so that no data can
be lost.  Historical data is resent until it is successfully received.

The syntax for specifying streamers is straightforward.  You just specify
what data streams you want to send and whether you want to send them as realtime
or historical data::

    [manual] (signed | realtime) streamer on <selector>;

The manual keyword will be covered in the next tutorial but it gives the user
more flexibility in when the streamer tries to send data.  By default streamers
are "automatic", which means they try to send data whenever it is available.

You choose whether its data is realtime or historical by specifying the
keywords `realtime` or `signed` and finally you choose what data to send by
specify a **Stream Selector**.  This can be just the name of a stream or it can
be a wildcard like **all outputs**.

Here are a few examples::

    manual signed streamer on all outputs;
    realtime streamer on unbuffered 10;

These two streamer say that we would like to report realtime data whenever it
is available on the `unbuffered 10` stream and we would also like to send
all `output` streams as historical data that will be triggered manually.

In the next tutorial, we will cover how to trigger manual streamers from a
sensor graph.

Next Steps
##########

Read about how to write more advanced sensor graphs as well as how to program
or test them with actual devices.
