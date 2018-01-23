"""Sensor graph nodes.

Sensor graph nodes are the basic input/output unit of a sensor graph.
They take a number of inputs, run them through a translation function
and create an output.  The output can then be linked to other nodes
to create a graph structure (hence the name SensorGraph).
"""

from builtins import str
from future.utils import python_2_unicode_compatible
from .exceptions import TooManyInputsError, TooManyOutputsError, ProcessingFunctionError
from iotile.core.exceptions import ArgumentError
from .walker import InvalidStreamWalker
from copy import copy


@python_2_unicode_compatible
class InputTrigger(object):
    """A triggering condition for a graph node input.

    Node inputs can trigger either based on how many readings are
    available to read, or based on the value of the last reading.

    The trigger is evaluated as:

    <source> <comparator> <reference_value>

    Args:
        source (str): either count or value to trigger on either
            a count of available readings or the value of the
            last reading.
        comparator (str): a string describing the comparator.
            Possible options are >, >=, <, =, <=
        reference_value (int): The value to compare source against.
    """

    def __init__(self, source, comparator, reference_value):
        source = str(source)
        if source not in [u'count', u'value']:
            raise ArgumentError("Unknwon source for input trigger, should be count or value", source=source)

        self.use_count = False
        if source == u'count':
            self.use_count = True

        known_comps = {
            u'>': self._gt_comp,
            u'>=': self._ge_comp,
            u'<': self._lt_comp,
            u'<=': self._le_comp,
            u'==': self._eq_comp
        }

        comparator = str(comparator)
        if comparator not in known_comps:
            raise ArgumentError("Unkown comparison function for input trigger", comparator=comparator)

        self.comp_function = known_comps[comparator]
        self.comp_string = comparator
        self.reference = reference_value

    def format_trigger(self, stream):
        """Create a user understandable string like count(stream) >= X.

        Args:
            stream (DataStream): The stream to use to format ourselves.

        Returns:
            str: The formatted string
        """

        src = u'value'
        if self.use_count:
            src = u'count'

        return u"{}({}) {} {}".format(src, stream, self.comp_string, self.reference)

    def triggered(self, walker):
        """Check if this input is triggered on the given stream walker.

        Args:
            walker (StreamWalker): The walker to check

        Returns:
            bool: Whether this trigger is triggered or not
        """

        if self.use_count:
            comp_value = walker.count()
        else:
            if walker.count() == 0:
                return False

            comp_value = walker.peek().value

        return self.comp_function(comp_value, self.reference)

    def _gt_comp(self, comp, ref):
        return comp > ref

    def _ge_comp(self, comp, ref):
        return comp >= ref

    def _lt_comp(self, comp, ref):
        return comp < ref

    def _le_comp(self, comp, ref):
        return comp <= ref

    def _eq_comp(self, comp, ref):
        return comp == ref

    def __str__(self):
        if self.use_count:
            return u"when count {} {}".format(self.comp_string, self.reference)

        return u"when value {} {}".format(self.comp_string, self.reference)


class FalseTrigger(object):
    """Simple trigger that always returns False."""

    def triggered(self, walker):
        return False


@python_2_unicode_compatible
class TrueTrigger(object):
    """Simple trigger that always returns True."""

    def triggered(self, walker):
        return True

    def __str__(self):
        return u"always"

    def format_trigger(self, stream):
        """Create a user understandable string like count(stream) >= X.

        Args:
            stream (DataStream): The stream to use to format ourselves.

        Returns:
            str: The formatted string
        """

        return u"{}".format(stream)


@python_2_unicode_compatible
class SGNode(object):
    """A node in a graph based processing structure.

    Each node has a function that it uses to consume inputs and
    create one output.  That output can be linked to the input
    of other nodes in a graph based structure.

    Args:
        stream (DataStream): The name of the data stream generated
            by this processing node
        model (DeviceModel): The device model that we are building this
            node for so we can constrain the maximum number of inputs
            and outputs.
    """

    AndTriggerCombiner = 0
    OrTriggerCombiner = 1

    def __init__(self, stream, model):
        max_inputs = model.get('max_node_inputs')
        max_outputs = model.get('max_node_outputs')

        self.inputs = [(InvalidStreamWalker(None), FalseTrigger())]*max_inputs
        self.outputs = []
        self.stream = stream
        self.func_name = None
        self.func = None
        self.trigger_combiner = SGNode.OrTriggerCombiner

        self.max_outputs = max_outputs

    def connect_input(self, index, walker, trigger=None):
        """Connect an input to a stream walker.

        If the input is already connected to something an exception is thrown.
        Otherwise the walker is used to read inputs for that input.

        A triggering condition can optionally be passed that will determine
        when this input will be considered as triggered.

        Args:
            index (int): The index of the input that we want to connect
            walker (StreamWalker): The stream walker to use for the input
            trigger (InputTrigger): The trigger to use for the input.  If
                no trigger is specified, the input is considered to always be
                triggered (so TrueTrigger is used)
        """

        if trigger is None:
            trigger = TrueTrigger()

        if index >= len(self.inputs):
            raise TooManyInputsError("Input index exceeded max number of inputs", index=index, max_inputs=len(self.inputs), stream=self.stream)

        self.inputs[index] = (walker, trigger)

    def input_streams(self):
        """Return a list of DataStream objects for all singular input streams.

        This function only returns individual streams, not the streams that would
        be selected from a selector like 'all outputs' for example.

        Returns:
            list(DataStream): A list of all of the individual DataStreams that are inputs
                of the node.  Input selectors that select multiple streams are not included
        """

        streams = []

        for walker, _trigger in self.inputs:
            if walker.selector is None or not walker.selector.singular:
                continue

            streams.append(walker.selector.as_stream())

        return streams

    def find_input(self, stream):
        """Find the input that responds to this stream.

        Args:
            stream (DataStream): The stream to find

        Returns:
            (index, None): The index if found or None
        """

        for i, input_x in enumerate(self.inputs):
            if input_x[0].matches(stream):
                return i

    @property
    def num_inputs(self):
        """Return the number of connected inputs.

        Returns:
            int: The number of connected inputs
        """

        num = 0

        for walker, _ in self.inputs:
            if not isinstance(walker, InvalidStreamWalker):
                num += 1

        return num

    @property
    def num_outputs(self):
        """Return the number of connected outputs.

        Returns:
            int: The number of nodes connected to this node's output
        """

        return len(self.outputs)

    @property
    def free_outputs(self):
        """Return the number of free output connections.

        Returns:
            int: The number of additional outputs that could be connected.
        """

        return self.max_outputs - self.num_outputs

    def connect_output(self, node):
        """Connect another node to our output.

        This downstream node will automatically be triggered when we update
        our output.

        Args:
            node (SGNode): The node that should receive our output
        """

        if len(self.outputs) == self.max_outputs:
            raise TooManyOutputsError("Attempted to connect too many nodes to the output of a node", max_outputs=self.max_outputs, stream=self.stream)

        self.outputs.append(node)

    def triggered(self):
        """Test if we should trigger our operation.

        We test the trigger condition on each of our inputs and then
        combine those triggers using our configured trigger combiner
        to get an overall result for whether this node is triggered.

        Returns:
            bool: True if we should trigger and False otherwise
        """

        trigs = [x[1].triggered(x[0]) for x in self.inputs]

        if self.trigger_combiner == self.OrTriggerCombiner:
            return True in trigs

        return False not in trigs

    def set_func(self, name, func):
        """Set the processing function to use for this node.

        Args:
            name (str): The name of the function to use.  This is
                just stored for reference in case we need to serialize
                the node later.
            func (callable): A function that is called to process inputs
                for this node.  It should have the following signature:
                callable(input1_walker, input2_walker, ...)
                It should return a list of IOTileReadings that are then pushed into
                the node's output stream
        """

        self.func_name = name
        self.func = func

    def process(self, rpc_executor):
        """Run this node's processing function.

        Args:
            rpc_executor (RPCExecutor): An object capable of executing RPCs
                in case we need to do that.

        Returns:
            list(IOTileReading): A list of IOTileReadings with the results of
                the processing function or an empty list if no results were
                produced
        """

        if self.func is None:
            raise ProcessingFunctionError('No processing function set for node', stream=self.stream)

        results = self.func(*[x[0] for x in self.inputs], rpc_executor=rpc_executor)
        if results is None:
            results = []

        return results

    def __str__(self):
        # FIXME: This only works for a maximum of two inputs
        comb = u'||'

        if self.trigger_combiner == self.AndTriggerCombiner:
            comb = u'&&'

        # Handle one input nodes
        if isinstance(self.inputs[1][0], InvalidStreamWalker):
            return u'({} {}) => {} using {}'.format(self.inputs[0][0].selector, self.inputs[0][1], self.stream, self.func_name)

        return u'({} {} {} {} {}) => {} using {}'.format(self.inputs[0][0].selector, self.inputs[0][1], comb,
                                                         self.inputs[1][0].selector, self.inputs[1][1],
                                                         self.stream, self.func_name)
