from pyparsing import Optional, Word, Literal, Forward, alphas, nums, Group, Regex, ZeroOrMore, oneOf, restOfLine, dblQuotedString, StringEnd, Empty
from ..stream import DataStream, DataStreamSelector
from ..slot import SlotIdentifier


ident = None
rvalue = None
number = None
comp = None
config_type = None
slot_id = None
stream = None
selector = None
stream_trigger = None
time_interval = None
quoted_string = None
semi = None
comment = None

streamer_stmt = None

callrpc_stmt = None
simple_statement = None
generic_statement = None

block_id = None
block_bnf = None
statement = None
sensor_graph = None


def _create_primitives():
    global ident, rvalue, number, quoted_string, semi, time_interval, slot_id, comp, config_type, stream, comment, stream_trigger, selector

    if ident is not None:
        return

    semi = Literal(u';').suppress()
    ident = Word(alphas+u"_", alphas + nums + u"_")
    number = Regex(u'((0x[a-fA-F0-9]+)|[+-]?[0-9]+)').setParseAction(lambda s, l, t: [int(t[0], 0)])
    quoted_string = dblQuotedString

    comment = Literal('#') + restOfLine

    rvalue = number | quoted_string

    # Convert all time intervals into an integer number of seconds
    time_unit_multipliers = {
        u'second': 1,
        u'seconds': 1,
        u'minute': 60,
        u'minutes': 60,
        u'hour': 60*60,
        u'hours': 60*60,
        u'day': 60*60*24,
        u'days': 60*60*24,
        u'month': 60*60*24*30,
        u'months': 60*60*24*30,
        u'year': 60*60*24*365,
        u'years': 60*60*24*365,
    }

    config_type = oneOf('uint8_t uint16_t uint32_t int8_t int16_t int32_t uint8_t[] uint16_t[] uint32_t[] int8_t[] int16_t[] int32_t[] string')
    comp = oneOf('> < >= <= == ~=')

    time_unit = oneOf(u"second seconds minute minutes hour hours day days week weeks month months year years")
    time_interval = (number + time_unit).setParseAction(lambda s, l, t: [t[0]*time_unit_multipliers[t[1]]])

    slot_id = Literal(u"controller") | (Literal(u'slot') + number)
    slot_id.setParseAction(lambda s,l,t: [SlotIdentifier.FromString(u' '.join([str(x) for x in t]))])

    stream_modifier = Literal("system") | Literal("user") | Literal("combined")

    stream = Optional(Literal("system")) + oneOf("buffered unbuffered input output counter constant") + number + Optional(Literal("node"))
    stream.setParseAction(lambda s,l,t: [DataStream.FromString(u' '.join([str(x) for x in t]))])

    all_selector = Optional(Literal("all")) + Optional(stream_modifier) + oneOf("buffered unbuffered inputs outputs counters constants") + Optional(Literal("nodes"))
    all_selector.setParseAction(lambda s,l,t: [DataStreamSelector.FromString(u' '.join([str(x) for x in t]))])
    one_selector = Optional(Literal("system")) + oneOf("buffered unbuffered input output counter constant") + number + Optional(Literal("node"))
    one_selector.setParseAction(lambda s,l,t: [DataStreamSelector.FromString(u' '.join([str(x) for x in t]))])

    selector = one_selector | all_selector

    trigger_comp = oneOf('> < >= <= ==')
    stream_trigger = Group((Literal(u'count') | Literal(u'value')) + Literal(u'(').suppress() - stream - Literal(u')').suppress() - trigger_comp - number).setResultsName('stream_trigger')


def _create_simple_statements():
    global ident, rvalue, simple_statement, semi, comp, number, slot_id, callrpc_stmt, generic_statement, streamer_stmt, stream, selector

    if simple_statement is not None:
        return

    meta_stmt = Group(Literal('meta').suppress() + ident + Literal('=').suppress() + rvalue + semi).setResultsName('meta_statement')
    require_stmt = Group(Literal('require').suppress() + ident + comp + rvalue + semi).setResultsName('require_statement')
    set_stmt = Group(Literal('set').suppress() + (ident | number) + Literal("to").suppress() + rvalue + Optional(Literal('as').suppress() + config_type) + semi).setResultsName('set_statement')
    callrpc_stmt = Group(Literal("call").suppress() + (ident | number) + Literal("on").suppress() + slot_id + Optional(Literal("=>").suppress() + stream('explicit_stream')) + semi).setResultsName('call_statement')
    streamer_stmt = Group(Optional(Literal("manual")('manual')) + Optional(oneOf(u'encrypted signed')('security')) + Optional(Literal(u'realtime')('realtime')) + Literal('streamer').suppress() -
                          Literal('on').suppress() - selector('selector') - Optional(Literal('to').suppress() - slot_id('explicit_tile')) - Optional(Literal('with').suppress() - Literal('streamer').suppress() - number('with_other')) - semi).setResultsName('streamer_statement')
    copy_stmt = Group(Literal("copy") - Optional(oneOf("all count average")('modifier')) - Optional(stream('explicit_input')) - Literal("=>") - stream("output") - semi).setResultsName('copy_statement')
    trigger_stmt = Group(Literal("trigger") - Literal("streamer") - number('index') - semi).setResultsName('trigger_statement')

    simple_statement = meta_stmt | require_stmt | set_stmt | callrpc_stmt | streamer_stmt | trigger_stmt | copy_stmt

    # In generic statements, keep track of the location where the match started for error handling
    locator = Empty().setParseAction(lambda s, l, t: l)('location')
    generic_statement = Group(locator + Group(ZeroOrMore(Regex(u"[^{};]+")) + Literal(u';'))('match')).setResultsName('unparsed_statement')


def _create_block_bnf():
    global block_bnf, time_interval, slot_id, statement, block_id, ident, stream

    if block_bnf is not None:
        return

    every_block_id = Group(Literal(u'every').suppress() - time_interval).setResultsName('every_block')
    when_block_id = Group(Literal(u'when').suppress() - Literal("connected").suppress() - Literal("to").suppress() - slot_id).setResultsName('when_block')
    config_block_id = Group(Literal(u'config').suppress() - slot_id).setResultsName('config_block')
    on_block_id = Group(Literal(u'on').suppress() + (stream_trigger | Group(stream).setResultsName('stream_always') | Group(ident).setResultsName('identifier'))).setResultsName('on_block')

    block_id = every_block_id | when_block_id | config_block_id | on_block_id

    block_bnf = Forward()
    statement = generic_statement | block_bnf

    block_bnf << Group(block_id + Group(Literal(u'{').suppress() + ZeroOrMore(statement) + Literal(u'}').suppress())).setResultsName('block')


def get_language():
    """Create or retrieve the parse tree for defining a sensor graph."""

    global sensor_graph, statement

    if sensor_graph is not None:
        return sensor_graph

    _create_primitives()
    _create_simple_statements()
    _create_block_bnf()

    sensor_graph = ZeroOrMore(statement) + StringEnd()
    sensor_graph.ignore(comment)

    return sensor_graph


def get_statement():
    """Create or retrieve the parse tree for a simple statement."""

    global simple_statement

    get_language()

    return simple_statement
