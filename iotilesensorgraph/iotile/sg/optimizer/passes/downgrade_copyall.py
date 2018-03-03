"""Convert copy_all to copy_latest whenever we can."""

from iotile.core.exceptions import ArgumentError
from iotile.sg.node import TrueTrigger, FalseTrigger, InputTrigger
from iotile.sg import DataStreamSelector, DataStream
import copy


class ConvertCopyAllToCopyLatest(object):
    """Run the copy_all to copy_latest optimization

    Copy_latest is much easier to optimize because we know it's always
    going to produce either 0 or 1 reading on the output.  Copy all on
    the other hand could produce many readings.

    There are some cases when we know that copy_all can be downgraded to
    copy_latest.

    The cases where we currently detect the operations as being the same
    are:

    - For unbuffered streams that are not counters,
      they are the same (i.e. input, unbuffered).
    - For counter streams whose selector is count == 1, they are the same
    - For counter streams whose selectror is always, they are the same
      since the counter stream starts with no readings and every time a
      reading is added

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

        did_downgrade = False

        for node, inputs, _outputs in sensor_graph.iterate_bfs():
            can_downgrade = False

            if node.func_name != u'copy_all_a':
                continue

            input_a, trigger_a = node.inputs[0]

            # We can always downgrade unbuffered non-counter
            if input_a.selector.match_type in (DataStream.InputType, DataStream.UnbufferedType):
                can_downgrade = True
            elif isinstance(trigger_a, InputTrigger) and trigger_a.comp_string == u'==' and trigger_a.use_count and trigger_a.reference == 1:
                can_downgrade = True
            elif isinstance(trigger_a, TrueTrigger) and not input_a.selector.buffered:
                # We can only downgrade an always trigger if we know the node before this will not
                # generate more than one reading at a time.  Since in that case, we get readings one at a
                # time and we don't accumulate them so there will be at most one reading to copy.
                # So, we need to check the node that produces input A to this node and see if we can
                # prove that it will produce at most one reading at a time.
                can_downgrade = True
                for in_node in inputs:
                    if input_a.matches(in_node.stream) and in_node.func_name == u'copy_all_a' and in_node.input_a.match_type not in (DataStream.InputType, DataStream.UnbufferedType):
                        can_downgrade = False
                        break

            if can_downgrade:
                did_downgrade = True
                node.set_func(u'copy_latest_a', sensor_graph.find_processing_function(u'copy_latest_a'))

        return did_downgrade
