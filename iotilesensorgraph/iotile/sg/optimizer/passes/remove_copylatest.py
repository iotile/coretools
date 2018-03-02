"""Remove unnecessary nodes with the copy_latest_a function.

These nodes are only necessary if there are not enough output links
on the input node to accomodate all outputs or if there is a
triggering condition on an input other than intput A that triggers
the node to copy.
"""
import logging
from iotile.core.exceptions import ArgumentError
from iotile.sg.node import TrueTrigger, FalseTrigger, InputTrigger
from iotile.sg import DataStreamSelector
import copy


class RemoveCopyLatestPass(object):
    """Run the remove copy latest optimization pass.

    Args:
        sensor_graph (SensorGraph): The sensor graph to run
            the optimization pass on
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def run(self, sensor_graph, model):
        """Run this optimization pass on the sensor graph

        If necessary, information on the device model being targeted
        can be found in the associated model argument.

        Args:
            sensor_graph (SensorGraph): The sensor graph to optimize
            model (DeviceModel): The device model we're using
        """

        # Try to remove a node whose operation is copy_latest_a
        # It inherently does nothing, so it can be removed if:
        # 1. There is only one input triggering it
        # 2. The input is from another node (i.e. not a global sg input)
        # 3. The type of the input is the same as the type of the output
        # 4. There are enough output links in the input node to
        #    handle all of the downstream connections.  Note that we will
        #    reclaim one free output when we do the replacement.
        #    If there are multiple nodes that write to this input, all
        #    must have an available output.
        # 5. The stream is not a sensor graph output
        # 6. The trigger conditions for both inputs and outputs are either
        #    count based or always or value based with the same value.
        #
        # For each node, check if 1-6 are valid so we can remove it

        found_node = None
        found_inputs = None
        found_outputs = None

        for node, inputs, outputs in sensor_graph.iterate_bfs():
            if node.func_name != u'copy_latest_a':
                continue

            # Check 1
            if node.num_inputs != 1:
                continue

            # Check 2
            if len(inputs) == 0:
                continue

            can_combine = True
            for curr_input in inputs:
                # Check 3
                if curr_input.stream.stream_type != node.stream.stream_type:
                    can_combine = False
                    break

                # Check 4 (keep in mind we free up one output when we do the swap)
                if (curr_input.free_outputs + 1) < len(outputs):
                    can_combine = False
                    break

            if not can_combine:
                continue

            # Check 5
            if sensor_graph.is_output(node.stream):
                continue

            # Check 6
            for out in outputs:
                i = out.find_input(node.stream)
                _, trigger = out.inputs[i]

                # We can't merge things that could result in producing
                # multiple readings at a time since then combining the
                # trigger might change what number of outputs are
                # produced since:
                # trigger every 600 copy_latest then trigger every 1 copy_all
                # would produce one reading every 600 ticks.
                #
                # but:
                # trigger every 1 copy_latest then trigger every 600 copy_all
                # would produce 600 readings one every 600 ticks.
                if out.func_name == u'copy_all_a':
                    can_combine = False
                    break

                if not self._can_combine(node.inputs[0][1], trigger):
                    can_combine = False
                    break

            if not can_combine:
                continue

            found_node = node
            found_inputs = inputs
            found_outputs = outputs
            break

        if found_node is None:
            return False

        sensor_graph.nodes.remove(found_node)

        for input_node in found_inputs:
            input_node.outputs.remove(found_node)

        for output in found_outputs:
            i = output.find_input(found_node.stream)
            old_walker, old_trigger = output.inputs[i]

            new_trigger = self._try_combine(found_node.inputs[0][1], old_trigger)
            new_walker = sensor_graph.sensor_log.create_walker(DataStreamSelector.FromString(str(found_node.inputs[0][0].selector)))
            sensor_graph.sensor_log.destroy_walker(old_walker)

            output.inputs[i] = (new_walker, new_trigger)

            for input_node in found_inputs:
                input_node.connect_output(output)

        if found_node in sensor_graph.roots:
            sensor_graph.roots.remove(found_node)

        sensor_graph.sensor_log.destroy_walker(found_node.inputs[0][0])
        return True

    def _can_combine(self, trigger1, trigger2):
        """Check if we can combine two triggers together.

        Return:
            bool
        """

        try:
            self._try_combine(trigger1, trigger2)
            return True
        except ArgumentError:
            pass

        return False

    def _try_combine(self, trigger1, trigger2):
        """Try to combine two triggers together.

        This function assumes a node structure of
            trigger1 -> copy_latest -> trigger2
        and tries to find a single trigger that can replace this
        as:
            trigger3
        with no copy latest

        Throws:
            ArgumentError: there is no way to combine these two
                triggers into one

        Returns:
            object: The combined trigger if possible
        """

        if isinstance(trigger1, FalseTrigger) or isinstance(trigger2, FalseTrigger):
            return FalseTrigger()

        if isinstance(trigger1, TrueTrigger):
            return copy.copy(trigger2)

        if isinstance(trigger2, TrueTrigger):
            return copy.copy(trigger1)

        # Otherwise these are both InputTrigger instances, which we can only
        # combine in certain cases.

        # If the triggers are count == X and count == Y, we can combine them to
        # count == X*Y
        #
        # If the triggers are count >= X and count == 1 then this is the same
        # as just count >= X since every time that triggers the next node
        # will trigger immediately and consume everything down to 0.
        if trigger1.use_count and trigger2.use_count:
            if trigger1.comp_string == u'==' and trigger2.comp_string == u'==':
                combined_ref = trigger1.reference * trigger2.reference

                # Make sure we won't overflow
                if combined_ref <= 0xFFFFFFFF:
                    return InputTrigger(u'count', u'==', combined_ref)
            elif trigger1.comp_string in [u">=", u"<=", u"<", u">"] and trigger2.comp_string == u"==" and trigger2.reference == 1:
                return InputTrigger(u'count', trigger1.comp_string, trigger1.reference)

        elif trigger1.use_count is False and trigger2.use_count is False:
            # If these are value triggers then we can combine them if the
            # value is the same
            if trigger1.comp_string == u"==" and trigger2.comp_string == u"==" and trigger1.reference == trigger2.reference:
                return InputTrigger(u"value", trigger1.comp_string, trigger1.reference)

        raise ArgumentError("Cannot combine triggers")
