"""A snippet is a series of commands that can be piped into the iotile tool connected to a device."""

from binascii import hexlify

def format_snippet(sensor_graph):
    """Format this sensor graph as iotile command snippets.

    This includes commands to reset and clear previously stored
    sensor graphs.

    Args:
        sensor_graph (SensorGraph): the sensor graph that we want to format
    """

    output = []

    # Clear any old sensor graph
    output.append("disable")
    output.append("clear")
    output.append("reset")

    # Load in the nodes
    for node in sensor_graph.dump_nodes():
        output.append('add_node "{}"'.format(node))

    # Load in the streamers
    for streamer in sensor_graph.streamers:
        line = "add_streamer '{}' '{}' {} {} {}".format(streamer.walker.selector, streamer.dest, streamer.automatic, streamer.format, streamer.report_type)

        if streamer.with_other is not None:
            line += ' --withother {}'.format(streamer.with_other)

        output.append(line)

    # Load all the constants
    for stream, value in sensor_graph.constant_database.items():
        output.append("set_constant '{}' {}".format(stream, value))

    # Persist the sensor graph
    output.append("persist")

    output.append("back")

    # If we have an app tag and version set program them in
    app_tag = sensor_graph.metadata_database.get('app_tag')
    app_version = sensor_graph.metadata_database.get('app_version')

    if app_tag is not None:
        if app_version is None:
            app_version = "0.0"

        output.append("test_interface")
        output.append("set_version app %d --version '%s'" % (app_tag, app_version))
        output.append("back")

    # Load in the config variables if any
    output.append("config_database")
    output.append("clear_variables")

    for slot, conf_vars in sensor_graph.config_database.items():
        for conf_var, conf_def in conf_vars.items():
            conf_type, conf_val = conf_def

            if conf_type == 'binary':
                conf_val = 'hex:' + hexlify(conf_val)
            elif isinstance(conf_val, str):
                conf_val = '"%s"' % conf_val

            output.append("set_variable '{}' {} {} {}".format(slot, conf_var, conf_type, conf_val))

    # Restart the device to load in the new sg
    output.append("back")
    output.append("reset")

    return "\n".join(output) + '\n'
