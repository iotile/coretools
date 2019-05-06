"""A machine readable ascii format for storing config information from a sensor graph.

The iotile-sensorgraph package works on .sgf files which contain both data flow
definitions run using an embedded sensor graph engine on an IOTile Device and
static configuration information that defines how the IOTile device is configured.
"""

from binascii import hexlify
from iotile.core.utilities.command_file import CommandFile


def format_config(sensor_graph):
    """Extract the config variables from this sensor graph in ASCII format.

    Args:
        sensor_graph (SensorGraph): the sensor graph that we want to format

    Returns:
        str: The ascii output lines concatenated as a single string
    """

    cmdfile = CommandFile("Config Variables", "1.0")

    for slot in sorted(sensor_graph.config_database, key=lambda x: x.encode()):
        for conf_var, conf_def in sorted(sensor_graph.config_database[slot].items()):
            conf_type, conf_val = conf_def

            if conf_type == 'binary':
                conf_val = 'hex:' + hexlify(conf_val).decode("utf-8")

            cmdfile.add("set_variable", slot, conf_var, conf_type, conf_val)

    return cmdfile.dump()
