Advanced SensorGraph Usage
--------------------------

The last few tutorials covered the basics of how to write and simulate a sensor
graph. Now we're going to dive deeper into how to actually program a sensor
graph into a device using the iotile tool.  We're also going to cover how to
semihost a sensor graph where it runs on your computer but executes its 
RPCs on an actual IOTile device.

Goals
#####

1. Understand how to use the `iotile-sgcompile` program to display detailed 
   information on how a sensor graph works internally.
2. Understand the different kinds of streams and their uses
3. Understand how the sensor graph optimizer works and how to disable it 
   if needed.

Background
##########

We've seen how the SensorGraph language lets you specify at a very high level
how an IOTile device should be wired together to create a specific application.
You can specify how data should be collected by the device, what triggers should
cause actions to be executed and what data should be sent remotely for long 
term storage.

It's not necessarily clear though, why the language is called Sensor*Graph*. 
There's nothing particularly graph-like about the language as we've discussed it
so far.  However, the low level representation of the SensorGraph files that 
you write is actually a data processing graph where DataStreams are linked
together with processing functions to create complex chains of actions that
are simultaneously powerfully expressive and also easy to verify and understand.

Conceptually a sensor graph is made up of **Nodes** that correspond with
processing functions.  Each Node has several inputs that are each FIFOs so
multiple values can accumulate in an input and then be processed at once. 
The node has a **Trigger** that determines when it should run its
processing function on its inputs to produce an output.

The input FIFOs are called **Stream Walkers**.  Stream walkers are FIFOs
that are attached to a DataStream and remember the last value in that Stream
that each node has processed.  You can have multiple stream walkers on the
same stream that walk that stream at a different rate.  For example, say you
have a stream named 'output 1' that has two nodes connected to it.  The first
node processes readings one at a time every time they come in so its stream
walker will always stay up to date with the latest reading.  The second node,
 though, could be configured to average its input every 60 readings, so its 
 stream walker would accumulate 60 readings before the node fires.  

The key point is that whenever a reading is pushed into a stream, it is as if
a copy of the value is pushed to each stream walker
separately and those stream walkers function as independent FIFOs.  So, one
could have 60 readings in it while another has 5 even though the have the 
same stream name.

In this tutorial we're going to use the iotile-sgcompile program to compile
our high level SensorGraph down into the actual graph nodes and edges that 
are simulated and programmed into a physical IOTile device.

Key Concepts
############

SensorGraph Node
	A node in the underlying graph of processing functions that make up a 
	sensor graph.  Nodes have a single processing function, up to 2 inputs and
	a single output. They also have a set of triggering conditions that
	determine when the node triggers its processing function based on its
	input conditions.  When the node triggers it uses its processing function
	to transform its inputs into zero or more outputs.

Node Trigger
	A specific triggering condition that determines when a Node activates
	is processing function.  Triggers can be based either on the latest value
	present in an input or on the number of readings accumulated in the 
	input Stream Walker.

Stream Walker
	A FIFO that attaches to a DataStream and walks over its values.  Walkers
	keep track of where they are in a DataStream indepedent of all other 
	Stream Walkers attached to that same stream so they can walk streams at 
	different rates.

Seeing the Actual Graph
#######################

Consider the following sensor graph::

	every 10 minutes
	{
		call 0x8000 on slot 1 => unbuffered 2;
	}

	on value(unbuffered 2) == 5
	{
		call 0x9000 on slot 2;
	}

Let's compile it using `iotile-sgcompile` and see the underlying graph that
is produced (save the above example as `example.sgf`)::

	(iotile) > iotile-sgcompile example.sgf -f nodes
	(system input 2 always) => counter 1024 using copy_all_a
	(system input 3 always) => counter 1025 using copy_all_a
	(counter 1024 when count >= 60) => counter 1026 using copy_latest_a
	(counter 1026 when count == 1 && constant 1024 always) => unbuffered 2 using call_rpc
	(unbuffered 2 when value == 5) => unbuffered 1024 using copy_latest_a
	(unbuffered 1024 when count == 1 && constant 1025 always) => unbuffered 1025 using call_rpc

First node that we called the `iotile-sgcompile` program, passed it our
sensor graph file and asked for the output  in the 'node' format, which is the 
generated graph.

There were 6 nodes generated in the graph.  All the nodes have the same 
format::
	
	(<input 1> trigger [&&, ||] [<input 2 trigger]) => <output> using <processor>

Basically there are written as `(inputs) => output` where there can either be
one or two input streams and always a single output stream.  The processing
function to use is also explicitly specified by name.  

Let's dissect the first node::

	(system input 2 always) => counter 1024 using copy_all_a

In prose, this says::

	Always, when there is a reading in the 'system input 2' stream, run the
	function copy_all_a that copies it to the 'counter 1024' stream.

This node will always activate whenever new data is placed into 
`system input 2`.  

.. note::

	`system input 2` is special in that it is a 10 second tick supplied by the
	sensor graph engine that is used internally to create whatever timers are 
	needed to run other nodes at specific intervals.

Let's look at a more complicated node::

	(counter 1026 when count == 1 && constant 1024 always) => unbuffered 2 using call_rpc

In prose, this says::

	Whenever there is exactly one reading in the counter 1026 stream, run the 
	function call_rpc.  Call_rpc uses its second input (the value in constant
	1024) to determine what RPC to call on what tile.  Technically there 
	are two triggers for this node combined with the AND function:

	count(counter 1024) == 1 AND always

	The always trigger is always true so the node fires whenever
	count(counter 1024) == 1

Triggers can be based on the number of readings available in a stream or they 
can be based on the value of the latest reading in a stream as in::

	(unbuffered 2 when value == 5) => unbuffered 1024 using copy_latest_a

In prose this says::

	Whenever the latest value in the `unbuffered 2` stream is equal to 5,
	copy it to unbuffered 1024.

.. important::

	When a node is triggered, it typically consumes all of the data that is 
	pending on all of its inputs, returning their counts back to 0 (except 
	for constant streams that are inexhaustible).  

	So if you have a node like:

	(counter 1 when count >= 60) => output 1 using copy_latest_a

	This will fire exactly once for every 60 readings added to `counter 1`
	because each time it runs it will reset the count on its input StreamWalker
	back to zero.

Different Kinds of Streams 
##########################

There are currently 6 different classes of streams.  Their own differences are 
in how many past values are remembered and whether a count is kept
of how many readings have been pushed to the stream. 

Buffered Streams
	Buffered streams can be considered as normal FIFOs.  All readings pushed to
	a buffered stream are remembered until the device runs out of storage space
	and the count of available readings corresponds with the number of readings
	that have been pushed to the stream with each pop() operation returning the
	next oldest reading.

Unbuffered Streams
	Unbuffered streams only ever store 1 value.  They have no space to store
	historical data and they also don't lie to you about how many readings are
	available so an unbuffered stream can only ever have a count of 0 or 1
	depending on whether it has data available or not.

Counter Streams
	Counter streams are unbuffered so they only store a single reading, however,
	they keep an accurate count of how many times they have been pushed to and
	allow you to pop from them that many times, each time returning the same 
	latest value that was last pushed.  Counter streams are primarily useful
	for creating efficient timers but their values are typically not used, just
	their counts. 

Input Streams
	Input streams are the global inputs to a sensor graph.  They are the roots
	of the processing graph.  The only entry points for new data into a sensor
	graph are inputs.  They are unbuffered.

Output Streams
	Output streams are buffered streams but stored in a different region of 
	persistent storage from buffered streams so that overflowing the buffered
	storage region does not overflow the output storage.  As the name suggests,
	output streams typically represent the outputs of a device that should be 
	saved historically.

Constant Streams
	Constant streams always return a constant value.  They can never be 
	exhausted and are useful for two primary purposes.  The first is to embed
	constant data in a sensor graph like what RPCs to call.  The second is to
	create latches that are used to derive timers gated on specific events.

	For example, if the user creates a `when connected` block that should call
	an RPC every second while a user is connected to the device, internally a
	constant stream is used to create a latch that is 1 when the user is
	connected and 0 otherwise.  This is combined with a 1 second clock to 
	create a derived 1 second clock that is only active when a user is
	connected.

Users need to explicitly specify the types of each stream they want to allocate
since it's not possible for the SensorGraph compiler to infer which would be 
most appropriate in most cases.

Understanding the Optimizer
###########################

Since SensorGraphs allow they user to very explicitly say what should happen
as data comes into the device and what data is considered an output, the
compiler can aggressively optimize the underlying graph as long as it 
guarantees that the behavior for each input is unchanged in so far as the 
outputs are concerned.

The optimizer works by taking an initial sensor graph and either removing
or modifying nodes and triggers if it can prove that the resulting 
configuration is identical to the initial one in terms of user visible 
behavior. The optimizer makes no assumptions about what happens inside of 
an RPC and just works on the sensor graph structure itself.

If you want to see what the optimizer does or need to disable it, you can
specify the `--disable-optimizer` flag to the sensorgraph compiler.

Next Steps
##########

After finishing all of these tutorials you should be ready to build your 
own IOTile based data gathering and control system by putting all of the 
pieces we've covered together to fit your needs.