"""Convert count == 1 triggers that don't have other streams as inputs on unbuffered streams to always.
"""

from iotile.core.exceptions import ArgumentError
from iotile.sg.node import TrueTrigger, FalseTrigger, InputTrigger
from iotile.sg import DataStreamSelector, DataStream
import copy


class ConvertCountOneToAlways(object):
    """Run the remove copy latest optimization pass.

    If there is a node whose input is:
    (unbuffered x when count == 1) => X

    This can be turned into:
    (unbuffered x always)

    Since the node will only be checked when there is data and
    if there is data the count will equal 1.

    This works for unbuffered and input type streams.

    Args:
        sensor_graph (SensorGraph): The sensor graph to run
            the optimization pass on
    """

    def __init__(self):
        pass

    def run(self, sensor_graph, model):
        """Run this optimization pass on the sensor graph

        If necessary, information on the device model being targeted
        can be found in the associated model argument.

        Args:
            sensor_graph (SensorGraph): The sensor graph to optimize
            model (DeviceModel): The device model we're using
        """

        # This check can be done if there is 1 input and it is count == 1
        # and the stream type is input or unbuffered

        for node, inputs, outputs in sensor_graph.iterate_bfs():
            if node.num_inputs != 1:
                continue

            input_a, trigger_a = node.inputs[0]
            if input_a.selector.match_type not in [DataStream.InputType, DataStream.UnbufferedType]:
                continue

            if not isinstance(trigger_a, InputTrigger):
                continue

            if trigger_a.comp_string != u'==':
                continue

            if not trigger_a.use_count:
                continue

            if trigger_a.reference != 1:
                continue

            # here we're looking at count input | unbuffered X == 1
            node.inputs[0] = (input_a, TrueTrigger())
