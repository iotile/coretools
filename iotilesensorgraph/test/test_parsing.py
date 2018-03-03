import os
import pytest
from iotile.sg.exceptions import SensorGraphSyntaxError
from iotile.sg import DataStream, SlotIdentifier, DataStreamSelector
from iotile.sg.parser import SensorGraphFileParser
import iotile.sg.parser.language as language


@pytest.fixture
def parser():
    return SensorGraphFileParser()


def get_path(name):
    return os.path.join(os.path.dirname(__file__), 'sensor_graphs', name)


def test_language_constructs():
    """Make sure the basic sensor graph language constructs work."""

    # Create the parser
    language.get_language()

    # Test time interval parsing
    parsed = language.time_interval.parseString('1 day')
    assert parsed.asList()[0] == 60*60*24

    # Test block id parsing
    parsed = language.block_id.parseString('every 1 day')
    assert parsed.asList()[0][1][0] == 60*60*24

    # Test block parsing
    parsed = language.block_bnf.parseString('every 1 day {}')
    assert parsed.asList()[0][0][1][0] == 60*60*24

    # Test stream parsing
    parsed = language.stream.parseString('output 1')
    assert isinstance(parsed.asList()[0], DataStream)

    # Test call_rpc statement
    parsed = language.callrpc_stmt.parseString(u'call 0x4001 on slot 1 => output 1;')
    assert parsed.asList()[0][0] == 0x4001

    # Test block with statement parsing
    parsed = language.block_bnf.parseString(u'every 1 day { call 0x5001 on slot 2 => output 1; }')
    assert parsed.asList()[0][0][1][0] == 60*60*24

    # Test parsing stream_trigger
    parsed = language.stream_trigger.parseString(u'value(input 2) == 10')
    assert parsed[0].getName() == u'stream_trigger'

    parsed = language.stream_trigger.parseString(u'count(output 1) <= 10')
    assert parsed[0].getName() == u'stream_trigger'

    # Test parsing on block with identifier
    parsed = language.block_bnf.parseString(u'on test_identifier {}')
    print(parsed)
    assert parsed[0][0][1][0][0].getName() == u'identifier'
    assert parsed[0][0][1][0][0][0] == u'test_identifier'

    parsed = language.block_bnf.parseString(u'on value(input 2) >= 5 {}')
    assert parsed[0][0][1][0][0].getName() == u'stream_trigger'
    assert parsed[0][0][1][0][0][0] == u'value'
    assert parsed[0][0][1][0][0][1] == DataStream.FromString('input 2')
    assert parsed[0][0][1][0][0][2] == u'>='
    assert parsed[0][0][1][0][0][3] == 5

    # Test parsing on block with 2 conditions
    parsed = language.block_bnf.parseString(u'on test_identifier and hello_id {}')
    assert parsed[0][0][1][0][0].getName() == u'identifier'
    assert parsed[0][0][1][0][0][0] == u'test_identifier'
    assert parsed[0][0][1][2][0].getName() == u'identifier'
    assert parsed[0][0][1][2][0][0] == u'hello_id'
    assert parsed[0][0][1][1] == u'and'

    parsed = language.block_bnf.parseString(u'on test_identifier or value(constant 1) == 2 {}')
    assert parsed[0][0][1][0][0].getName() == u'identifier'
    assert parsed[0][0][1][0][0][0] == u'test_identifier'
    assert parsed[0][0][1][1] == u'or'

    # Test parsing subtract statements
    parsed = language.subtract_stmt.parseString(u"subtract constant 1 => unbuffered 2, default 10;")
    assert parsed[0].getName() == 'subtract_statement'
    assert parsed[0][0] == DataStream.FromString('constant 1')
    assert parsed[0][1] == DataStream.FromString('unbuffered 2')
    assert parsed[0]['default'] == 10

    parsed = language.subtract_stmt.parseString(u"subtract constant 1 => unbuffered 2;")
    assert parsed[0].getName() == 'subtract_statement'
    assert parsed[0][0] == DataStream.FromString('constant 1')
    assert parsed[0][1] == DataStream.FromString('unbuffered 2')

    # Test parser streamer statements
    parsed = language.streamer_stmt.parseString(u'manual streamer on output 1;')
    assert parsed[0]['selector'] == DataStreamSelector.FromString('output 1')

    parsed = language.streamer_stmt.parseString(u'manual streamer on all system outputs;')
    assert parsed[0]['selector'] == DataStreamSelector.FromString('all system outputs')

    parsed = language.streamer_stmt.parseString(u'manual signed streamer on output 1 to slot 1;')
    assert parsed[0]['selector'] == DataStreamSelector.FromString('output 1')
    assert parsed[0]['explicit_tile'] == SlotIdentifier.FromString('slot 1')
    assert parsed[0]['security'] == u'signed'

    # Test parsing copy statements
    parsed = language.simple_statement.parseString(u'copy unbuffered 1 => unbuffered 2;')
    assert parsed[0]['explicit_input'][0] == DataStream.FromString('unbuffered 1')

    parsed = language.simple_statement.parseString(u'copy 15 => unbuffered 2;')
    assert parsed[0]['constant_input'] == 15

    parsed = language.simple_statement.parseString(u'copy 0x20 => unbuffered 2;')
    assert parsed[0]['constant_input'] == 0x20


def test_basic_parsing(parser):
    """Make sure we can parse a basic file without syntax errors."""

    parser.parse_file(get_path('basic_meta_file.sgf'))


def test_every_interval_block_parsing(parser):
    """Make sure we can parse an interval block."""

    parser.parse_file(get_path('basic_block.sgf'))


def test_statement_syntax_error(parser):
    """Make sure we get a nice syntax error when we type a bad statement."""

    with pytest.raises(SensorGraphSyntaxError) as exc_info:
        parser.parse_file(get_path('syntax_error_statement.sgf'))

    assert exc_info.value.params['line_number'] == 10


def test_nested_blocks(parser):
    """Make sure we can parse nested blocks."""

    parser.parse_file(get_path('nested_block.sgf'))

    assert parser.statements[0].location.line_no == 1
    assert parser.statements[0].children[0].location.line_no == 3
    assert parser.statements[0].children[0].children[0].location.line_no == 5


def test_ignoring_comments(parser):
    """Make sure we ignore comments."""

    parser.parse_file(get_path('comment_graph.sgf'))
