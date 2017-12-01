"""A machine readable ascii format for storing config information from a sensor graph.

The iotile-sensorgraph package works on .sgf files which contain both data flow
definitions run using an embedded sensor graph engine on an IOTile Device and
static configuration information that defines how the IOTile device is configured.
"""


def format_config(sensor_graph):
    """Extract the config variables from this sensor graph in ASCII format.

    Args:
        sensor_graph (SensorGraph): the sensor graph that we want to format

    Returns:
        str: The ascii output lines concatenated as a single string
    """

    output = []

    output.append("Config Variables")
    output.append("Format: 1.0")
    output.append("Type: ASCII")

    output.append("")

    for slot, conf_vars in sensor_graph.config_database.items():
        for conf_var, conf_def in conf_vars.items():
            conf_type, conf_val = conf_def
            output.append("set_variable {%s, %s, %s, %s}" % (slot, conf_var, conf_type, conf_val))

    return "\n".join(output) + '\n'
