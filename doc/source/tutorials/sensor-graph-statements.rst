The SensorGraph Language
------------------------

In this tutorial we're going to cover the main statements that you can write in
a sensor graph and what they do.

Goals
#####

1. Understand the key statements and blocks that make up the sensor graph
   language.

Background
##########

Like most languages, there are two kinds of elements in a sensor graph:
**Blocks** and **Statements**.

Blocks are `containers` for statements that are used to influence how the
statements are compiled.  All blocks consist of a single line that starts the
block and then zero or more statements contained in curly braces.

Statements are the actual commands that you want your IOTile device to run.
An empty block should have no effect.  All statements are a single line
and end with a semicolon.

Whitespace is ignored and comments may be included anywhere by prefacing a
line with the `#` character.  There are no C-like multiline comments.

Call Statements
###############

The most basic statement in a sensor graph is the `call` statement that calls
an RPC on a tile.  It's syntax is::

    call <rpc id> on <slot id> [=> <output stream>];
    call <rpc id> on controller [=> <output stream>];


.. important::

    The way to interpret a syntax definition like the one above is as follows:

    1. Anything in < > characters should be substituted in an actual command
       with a specific value.  It is just a placeholder.
    2. Any word or token not enclosed in < > characters must be literally
       included as part of the statement.  So, the keyword 'call' is required
       to start a call statement.
    3. Anything in a [ ] is optional.

This statement calls an RPC and optionally stores the result in
<output stream>.  It must be used inside of a block that allows triggering
statements like an `on` block or `every` block.

- <rpc id> should be a number.
- <slot id> should be a Slot Identifier.
- <output stream> should be Data Stream.

Copy Statements
###############

Copy statements copy a value from an input stream to an output stream::

    copy [all | count] [<input stream>] => <output stream>;

There are three ways you can copy things:

- `copy all` copies all readings that have not been processed yet from the input
  to the output stream.
- `copy` just copies the latest reading, ignoring any readings that may have
  been pushed before this statement triggered.
- `copy count` copies the number of readings currently in the input stream to
  the output stream.

If an explicit input stream is given, the data is copied from that stream,
otherwise there is always an implicit `trigger` stream defined in every block.

Implicit streams are useful inside `on blocks` since the `copy` command would
then work with the stream data that triggered the `on` condition.

Trigger Statements
##################

Trigger statements trigger the streaming of data inside manual streamers.  Their
usage is::

    trigger streamer <index>;

where <index> the index of the streamer you want to trigger, i.e. the first
streamer defined is index 0, the second is index 1, etc.  Trigger statements
are used to trigger manual streamer that don't try to automatically send
data whenever it is available.

Streamer Statements
###################

You define a streamer with a streamer statement::

    [manual] [realtime] streamer on <stream selector> [with streamer <index>];

If you specify a with clause, this streamer will trigger whenever the other streamer
identifier by index triggers.

You can specify either realtime or historical streamers by specifying realtime
or nothing.

The Every Block
###############

Every blocks run the commands inside of them every given time interval.  The
syntax is::

    every <time interval>
    {
        <statement 1>;
        ...
        <statement N>;
    }

Each statement (1 through N) will be called exactly once in order every time
interval.

- <time interval> should be a TimeInterval.

The On Block
############

On blocks run statements when a specific event happens.  They are like `if`
statements in other languages.  There are three possible triggers for an
on block::

    on value(<stream>) <op> <reference>
    {
        <statements>...
    }

    on count(<stream>) <op> <reference>
    {
        <statements>...
    }

    on <named event>
    {
        <statements>...
    }

The first on block triggers when a comparison between the value in a stream
and a constant reference value is true.

The second on block triggers when a comparison betwen the number of readings
in a stream and a constant reference value is true.

The third on block triggers when the specific named event happens.  Currently
the major named events a `connect` and `disconnect` which are defined only
inside of a `when connected` block.

The possible comparison operations are: `<, <=, ==, >, >=`.

You cannot nest another block inside of an on block.

The When Block
##############

When blocks let you conditionally trigger statements to happen only when a
user is connected to a device.  They can contains on blocks and every blocks,
which can in turn contain statements::

    when connected to <slot id>
    {
        on connect
        {
            <statements>
        }

        every <time interval>
        {
            <statements>
        }

        on disconnect
        {
            <statements>
        }
    }

The <slot id> is the tile that the user is connected to, in case there are
multiple communications tiles in a device.  This is almost always `controller`.

Statements inside the `on connect` block will run once when the user connects
and statements in `on disconnect` will run once when the user disconnects.

Statement inside an every block nested inside a when block will run every time
interval while a user is connected.

The Config Block
################

If you need to specify configuration variables for a tile, you do so with
`set` statements inside a `config` block::

    config <slot id>
    {
        set <variable id> to <value> as <type>;
        <more set statements>
    }

Each set statement stores a value that will be sent to the tile in <slot id>
every time it powers on.

- <variable id> is a 16 bit identifier for the config variable you want to set
- <value> should be an integer
- <type> must match the type of the variable defined for the tile you are trying
  to configure and be one of uint8_t, uint16_t, uint32_t

.. note::

    Currently, knowing what config variables to set and what types they are
    requires having access to a TileBus configuration file that is compiled as
    part of the tile's firmware.  In the future, these will be integrated with
    the SensorGraph language so that you will be able to specify config
    variables by name.

Slot Identifiers
################

Slot identifiers, when used as part of a statement specify the tile on which
an action should be taken.  Their syntax is::

    controller

    OR

    slot <number>


Time Intervals
##############

Time intervals can be specified down to 1 second precision in units of
seconds, minutes, hours, days, months or years::

    <number> (seconds | minutes | hours | days | months | years)

The unit can either be singular `second` or plural `seconds` with the same
meaning.  A month is considered to be 30 days exactly and a year is considered
to be 365 days exactly.

Stream Identifiers
##################

Stream Identifiers specify a single stream that data can go in::

    [system] (input | output | buffered | unbuffered | counter | constant) <number>

System streams are for internal use and should not be created by users but they
may be used for a variety of purposes.  The number must be between 0 and 1023
(inclusive).  Streams with numbers between 1024 and 2047 are allocated and
used internally by the sensor graph compiler.

The meanings of the various types of streams is covered in the next tutorial.

Stream Selectors
################

Stream selectors can either select a single stream or an entire class of
streams. Their syntax is::

    Stream Identifier

    OR

    all [system] (inputs | outputs | buffered | unbuffered | counters | constants)

Next Steps
##########

Read about advanced sensor graph topics and the low level details of how your
statements get turned into commands that IOTile devices can safely execute.
