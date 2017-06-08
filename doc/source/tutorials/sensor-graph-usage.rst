Testing and Deploying Sensor Graphs
-----------------------------------

In the last tutorial we covered the basics of how to make your own SensorGraph.
Now we are going to talk about how to program that sensor graph into an
IOTile device and how to "semihost" it so that you can test out the RPCs without
needing to fully program it into the device.

Goals
#####

1. Be able to semihost a sensor graph to test RPCs on an actual device
2. Be able to program a sensor graph onto a device for autonomous operation

Background
##########

There are two big parts to a sensor graph.  The first is the actual graph
that is coordinating what RPCs to call in order to acquire data or control
something.  The second is the underlying hardware that implements those RPCs.

Semihosting is running the sensor graph on your computer but delegating the 
RPCs to an actual hardware device.  This is useful because:

1. It means you can accelerate the passage of time to uncover subtle bugs that
   only manifest over a long period of operation.

2. It means you have access to all of the watch infrastructure of the simulator
   to see in detail what is happening in each stream.  This is more difficult
   once the sensor graph is actually embedded fully into a physical device.

Key Concepts
############

Semihosting

	Running a sensor graph on your computer while dispatching the RPCs to be 
	run on an actual device.  This device is connected to using the same
	HardwareManager based methods as the previous tutorials, so the device
	can be anywhere in the world or even virtual.

Semihosting a Sensor Graph
##########################

.. note:: 

	In order to run the following commands successfully, make sure that you 
	have the iotile-test package installed in order to have the right test
	virtual device::

		pip install -U iotile-test

Semihosting a sensor graph is really easy.  You just need to know two things:

- the port string for the DeviceAdapter that you want to use to connect to your
  IOTile device.  This is the same string that you use with the `iotile` tool
  (i.e. the port string in `iotile hw --port=<port string>`).
- the device id of the device that you want to connect to (like 0xABCD)

Simply pass the port as a `-p` argument to `iotile-sgrun` and the device id in 
a `-d` parameter and then simulate the sensor graph as normal.  The simulator
will connect to the device using the supplied information and run all RPCs 
on the device.  

For example, save the following sensor graph a `test.sgf`::

	every 10 seconds
	{
		call 0x8000 on controller => unbuffered 2;
		call 0x8002 on controller => unbuffered 2;
	}

	on value(unbuffered 2) == 5
	{
		call 0x8001 on slot 1 => output 1;
	}

We're going to semihost using a virtual device in `iotile-test called
(appropriately) sg_test.  The sg_test device just has two RPCs that are useful
for learning sensor graphs::

	controller: 0x8000 returns a random number between 0 and 100
	slot 1: 0x8001 returns the fixed integer 42

Let's try it out::

	(iotile) > iotile-sgrun test.sgf -p virtual:sg_test -d 1 -s 'run_time 1 minute' -w 'unbuffered 2'
	(      10 s) unbuffered 2: 80
	(      20 s) unbuffered 2: 59
	(      30 s) unbuffered 2: 25
	(      40 s) unbuffered 2: 45
	(      50 s) unbuffered 2: 24
	(      60 s) unbuffered 2: 1

We can also run for along time to see the random value trigger our second
sensor graph rule on unbuffered 2 == 5::

	(iotile) > iotile-sgrun test.sgf -p virtual:sg_test -d 1 -s 'run_time 1 hour' -w 'output 1'
	(     490 s) output 1: 42
	(     530 s) output 1: 42
	(     610 s) output 1: 42
	(    1290 s) output 1: 42
	(    1810 s) output 1: 42
	(    2360 s) output 1: 42
	(    2870 s) output 1: 42

Note the random timestamps since those were the random times that RPC 0x8000
on the controller returned 5.  Your results should vary.

.. important::
	
	You can still mock RPCs and those will override RPCs defined in the 
	semihosting device.  This can be useful for injecting unlikely conditions
	into more complicated sensor graphs for testing.

Let's mock RPC 0x8001 on slot 1 to return 50 rather than 42::

	(iotile) > iotile-sgrun test.sgf -p virtual:sg_test -d 1 -s 'run_time 1 hour' -w 'output 1' -m "slot 1:0x8001 = 50"
	(      40 s) output 1: 50
	(     390 s) output 1: 50
	(    2260 s) output 1: 50
	(    2760 s) output 1: 50
	(    3250 s) output 1: 50
	(    3360 s) output 1: 50

Programming Into a Device
#########################

Currently the best way to program a sensor graph into an actual device is to
use a combination of the `iotile-sgcompile` and `iotile` tools.  Given your
sensor graph, compile it with an output format of `snippet`.  This produces 
a list of commands that can be entered into the iotile tool to program 
the sensor graph onto a device.  You can just pipe this to the iotile tool
to program the sensor graph.

For example, let's look at the snippet corresponding to the `test.sgf` that
we created above::

	(iotile) > iotile-sgcompile test.sgf -f snippet
	disable
	clear
	reset
	add_node "(system input 2 always) => counter 1024 using copy_all_a"
	add_node "(system input 3 always) => counter 1025 using copy_all_a"
	add_node "(counter 1024 when count >= 1) => counter 1026 using copy_latest_a"
	add_node "(counter 1026 when count == 1 && constant 1024 always) => unbuffered 2 using call_rpc"
	add_node "(counter 1026 when count == 1 && constant 1025 always) => unbuffered 2 using call_rpc"
	add_node "(unbuffered 2 when value == 5) => unbuffered 1024 using copy_latest_a"
	add_node "(unbuffered 1024 when count == 1 && constant 1026 always) => output 1 using call_rpc"
	set_constant 'constant 1024' 557056
	set_constant 'constant 1025' 557058
	set_constant 'constant 1026' 753665
	persist
	back
	config_database
	clear_variables
	set_variable 'controller' 8192 uint32_t 1
	back
	reset

You can see how these are just iotile tool commands.  They are meant to be
entered in the `controller sensor_graph` context in the iotile tool while 
connected to an IOTile device.  

So the easiest way to program this into a device is::

	(iotile) > iotile-sgcompile test.sgf -f snippet | iotile hw --port=<port> connect <device id> controller sensor_graph

When the command terminates the new sensor graph will be programed into the 
device and the device will have reset itself to start running the sensor graph.

Next Steps
##########

You can cover more advanced sensor graph concepts in the next tutorial or 
start writing and testing your own sensor graphs!
