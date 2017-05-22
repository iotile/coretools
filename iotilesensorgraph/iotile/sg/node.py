"""Sensor graph nodes.

Sensor graph nodes are the basic input/output unit of a sensor graph.
They take a number of inputs, run them through a translation function
and create an output.  The output can then be linked to other nodes
to create a graph structure (hence the name SensorGraph).
"""


class SGNode(object):
    pass
