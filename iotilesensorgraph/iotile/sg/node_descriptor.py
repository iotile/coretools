"""A grammer for specifying sensor graph nodes."""

from builtins import str
from pyparsing import Word, Regex, nums, hexnums, Literal, Optional, Group, oneOf, QuotedString, ParseException
from .node import SGNode, InputTrigger
from .stream import DataStream, DataStreamSelector

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
    except ParseException as exc:
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
