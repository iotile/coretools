"""A machine parsable ascii representation of a sensor graph.

This format is directly loadable by the sensor_graph proxy using
the load_from_file method.  It closely mirrors the snippet format
with the arguments enclosed in brackets for easier parsing.
"""


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

    output = []

    output.append("Sensor Graph")
    output.append("Format: 1.0")
    output.append("Type: ASCII")

    output.append("")
    output.append("# Beginning of actual sensor graph data")

    # Clear any old sensor graph
    output.append(r"set_online {false}")
    output.append("clear")
    output.append("reset")

    # Load in the nodes
    for node in sensor_graph.dump_nodes():
        output.append('add_node {%s}' % node)

    # Load in the streamers
    for streamer in sensor_graph.streamers:
        other = 0xFF
        if streamer.with_other is not None:
            other = streamer.with_other

        args = "{}, {}, {}, {}, {}, {}".format(streamer.walker.selector, streamer.dest, streamer.automatic, streamer.format, streamer.report_type, other)
        line = "add_streamer {%s}" % args

        output.append(line)

    # Load all the constants
    for stream, value in sensor_graph.constant_database.items():
        output.append("push_reading {%s, %s}" % (stream, value))

    # Persist the sensor graph
    output.append("persist")
    output.append(r"set_online {true}")

    return "\n".join(output) + '\n'
