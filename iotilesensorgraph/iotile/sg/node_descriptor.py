"""A grammer for specifying sensor graph nodes."""

from __future__ import (unicode_literals, absolute_import, print_function)
from builtins import str
import struct
from pyparsing import Word, Regex, nums, hexnums, Literal, Optional, Group, oneOf, QuotedString, ParseException
from typedargs.exceptions import ArgumentError
from .node import SGNode, InputTrigger, FalseTrigger, TrueTrigger
from .stream import DataStream, DataStreamSelector
from .model import DeviceModel


number = Regex('((0x[a-fA-F0-9]+)|[0-9]+)')
combiner = (Literal('&&') | Literal('||'))
symbol = Regex('[a-zA-Z][a-zA-Z_]*')

stream_type = Optional(Literal('system')) + (Literal('input') | Literal('output') | Literal('buffered') | Literal("unbuffered") | Literal("constant") | Literal("counter")) + Optional(Literal("node").suppress())
stream = stream_type + number

trigger_type = (Literal('value') | Literal('count'))
trigger_op = oneOf('> < >= <= ==')

trigger = Literal('always') | (Literal('when').suppress() + trigger_type('type') + trigger_op('op') + number('reference'))

inputstring = stream('input_stream') + trigger

inputdesc2 = Literal('(').suppress() + inputstring('input_a') + combiner('combiner') + inputstring('input_b') + Literal(')').suppress()
inputdesc1 = Literal('(').suppress() + inputstring('input_a') + Literal(')').suppress()

inputdesc = inputdesc1('input1') | inputdesc2('input2')
graph_node = inputdesc + Literal('=>').suppress() + stream('node') + Literal('using').suppress() + symbol('processor')


def parse_node_descriptor(desc, model):
    """Parse a string node descriptor.

    The function creates an SGNode object without connecting its inputs and outputs
    and returns a 3-tuple:

    SGNode, [(input X, trigger X)], <processing function name>

    Args:
        desc (str): A description of the node to be created.
        model (str): A device model for the node to be created that sets any
            device specific limits on how the node is set up.
    """

    try:
        data = graph_node.parseString(desc)
    except ParseException:
        raise  # TODO: Fix this to properly encapsulate the parse error

    stream_desc = u' '.join(data['node'])

    stream = DataStream.FromString(stream_desc)
    node = SGNode(stream, model)

    inputs = []

    if 'input_a' in data:
        input_a = data['input_a']
        stream_a = DataStreamSelector.FromString(u' '.join(input_a['input_stream']))

        trigger_a = None
        if 'type' in input_a:
            trigger_a = InputTrigger(input_a['type'], input_a['op'], int(input_a['reference'], 0))

        inputs.append((stream_a, trigger_a))

    if 'input_b' in data:
        input_a = data['input_b']
        stream_a = DataStreamSelector.FromString(u' '.join(input_a['input_stream']))

        trigger_a = None
        if 'type' in input_a:
            trigger_a = InputTrigger(input_a['type'], input_a['op'], int(input_a['reference'], 0))

        inputs.append((stream_a, trigger_a))

    if 'combiner' in data and str(data['combiner']) == u'&&':
        node.trigger_combiner = SGNode.AndTriggerCombiner
    else:
        node.trigger_combiner = SGNode.OrTriggerCombiner

    processing = data['processor']
    return node, inputs, processing


def create_binary_descriptor(descriptor):
    """Convert a string node descriptor into a 20-byte binary descriptor.

    This is the inverse operation of parse_binary_descriptor and composing
    the two operations is a noop.

    Args:
        descriptor (str): A string node descriptor

    Returns:
        bytes: A 20-byte binary node descriptor.
    """

    func_names = {0: 'copy_latest_a', 1: 'average_a',
                  2: 'copy_all_a', 3: 'sum_a',
                  4: 'copy_count_a', 5: 'trigger_streamer',
                  6: 'call_rpc', 7: 'subtract_afromb'}

    func_codes = {y: x for x, y in func_names.items()}

    node, inputs, processing = parse_node_descriptor(descriptor, DeviceModel())

    func_code = func_codes.get(processing)
    if func_code is None:
        raise ArgumentError("Unknown processing function", function=processing)

    stream_a, trigger_a = inputs[0]
    stream_a = stream_a.encode()

    if len(inputs) == 2:
        stream_b, trigger_b = inputs[1]
        stream_b = stream_b.encode()
    else:
        stream_b, trigger_b = 0xFFFF, None

    if trigger_a is None:
        trigger_a = TrueTrigger()

    if trigger_b is None:
        trigger_b = TrueTrigger()

    ref_a = 0
    if isinstance(trigger_a, InputTrigger):
        ref_a = trigger_a.reference

    ref_b = 0
    if isinstance(trigger_b, InputTrigger):
        ref_b = trigger_b.reference

    trigger_a = _create_binary_trigger(trigger_a)
    trigger_b = _create_binary_trigger(trigger_b)

    combiner = node.trigger_combiner

    bin_desc = struct.pack("<LLHHHBBBB2x", ref_a, ref_b, node.stream.encode(), stream_a, stream_b, func_code, trigger_a, trigger_b, combiner)
    return bin_desc


def parse_binary_descriptor(bindata):
    """Convert a binary node descriptor into a string descriptor.

    Binary node descriptor are 20-byte binary structures that encode all
    information needed to create a graph node.  They are used to communicate
    that information to an embedded device in an efficent format.  This
    function exists to turn such a compressed node description back into
    an understandable string.

    Args:
        bindata (bytes): The raw binary structure that contains the node
            description.

    Returns:
        str: The corresponding string description of the same sensor_graph node
    """

    func_names = {0: 'copy_latest_a', 1: 'average_a',
                  2: 'copy_all_a', 3: 'sum_a',
                  4: 'copy_count_a', 5: 'trigger_streamer',
                  6: 'call_rpc', 7: 'subtract_afromb'}

    if len(bindata) != 20:
        raise ArgumentError("Invalid binary node descriptor with incorrect size", size=len(bindata), expected=20, bindata=bindata)

    a_trig, b_trig, stream_id, a_id, b_id, proc, a_cond, b_cond, trig_combiner = struct.unpack("<LLHHHBBBB2x", bindata)

    node_stream = DataStream.FromEncoded(stream_id)

    if a_id == 0xFFFF:
        raise ArgumentError("Invalid binary node descriptor with invalid first import", input_selector=a_id)

    a_selector = DataStreamSelector.FromEncoded(a_id)
    a_trigger = _process_binary_trigger(a_trig, a_cond)

    b_selector = None
    b_trigger = None
    if b_id != 0xFFFF:
        b_selector = DataStreamSelector.FromEncoded(b_id)
        b_trigger = _process_binary_trigger(b_trig, b_cond)

    if trig_combiner == SGNode.AndTriggerCombiner:
        comb = '&&'
    elif trig_combiner == SGNode.OrTriggerCombiner:
        comb = '||'
    else:
        raise ArgumentError("Invalid trigger combiner in binary node descriptor", combiner=trig_combiner)

    if proc not in func_names:
        raise ArgumentError("Unknown processing function", function_id=proc, known_functions=func_names)

    func_name = func_names[proc]

    # Handle one input nodes
    if b_selector is None:
        return '({} {}) => {} using {}'.format(a_selector, a_trigger, node_stream, func_name)

    return '({} {} {} {} {}) => {} using {}'.format(a_selector, a_trigger, comb,
                                                    b_selector, b_trigger,
                                                    node_stream, func_name)


def _process_binary_trigger(trigger_value, condition):
    """Create an InputTrigger object."""

    ops = {
        0: ">",
        1: "<",
        2: ">=",
        3: "<=",
        4: "==",
        5: 'always'
    }

    sources = {
        0: 'value',
        1: 'count'
    }

    encoded_source = condition & 0b1
    encoded_op = condition >> 1

    oper = ops.get(encoded_op, None)
    source = sources.get(encoded_source, None)

    if oper is None:
        raise ArgumentError("Unknown operation in binary trigger", condition=condition, operation=encoded_op, known_ops=ops)
    if source is None:
        raise ArgumentError("Unknown value source in binary trigger", source=source, known_sources=sources)

    if oper == 'always':
        return TrueTrigger()

    return InputTrigger(source, oper, trigger_value)


def _create_binary_trigger(trigger):
    """Create an 8-bit binary trigger from an InputTrigger, TrueTrigger, FalseTrigger."""

    ops = {
        0: ">",
        1: "<",
        2: ">=",
        3: "<=",
        4: "==",
        5: 'always'
    }

    op_codes = {y: x for x, y in ops.items()}
    source = 0

    if isinstance(trigger, TrueTrigger):
        op_code = op_codes['always']
    elif isinstance(trigger, FalseTrigger):
        raise ArgumentError("Cannot express a never trigger in binary descriptor", trigger=trigger)
    else:
        op_code = op_codes[trigger.comp_string]

        if trigger.use_count:
            source = 1

    return (op_code << 1) | source
