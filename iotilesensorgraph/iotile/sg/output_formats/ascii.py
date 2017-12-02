"""A machine parsable ascii representation of a sensor graph.

This format is directly loadable by the sensor_graph proxy using
the load_from_file method.  It closely mirrors the snippet format
with the arguments enclosed in brackets for easier parsing.
"""

from iotile.core.utilities.command_file import CommandFile


def format_ascii(sensor_graph):
    """Format this sensor graph as a loadable ascii file format.

    This includes commands to reset and clear previously stored
    sensor graphs.

    NB. This format does not include any required configuration
    variables that were specified in this sensor graph, so you
    should also output tha information separately in, e.g.
    the config format.

    Args:
        sensor_graph (SensorGraph): the sensor graph that we want to format

    Returns:
        str: The ascii output lines concatenated as a single string
    """

    cmdfile = CommandFile("Sensor Graph", "1.0")

    # Clear any old sensor graph
    cmdfile.add("set_online", False)
    cmdfile.add("clear")
    cmdfile.add("reset")

    # Load in the nodes
    for node in sensor_graph.dump_nodes():
        cmdfile.add('add_node', node)

    # Load in the streamers
    for streamer in sensor_graph.streamers:
        other = 0xFF
        if streamer.with_other is not None:
            other = streamer.with_other

        args = [streamer.walker.selector, streamer.dest, streamer.automatic, streamer.format, streamer.report_type, other]
        cmdfile.add('add_streamer', *args)

    # Load all the constants
    for stream, value in sensor_graph.constant_database.items():
        cmdfile.add("push_reading", stream, value)

    # Persist the sensor graph
    cmdfile.add("persist")
    cmdfile.add("set_online", True)

    return cmdfile.dump()
