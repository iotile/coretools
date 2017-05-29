import os
import pytest
import json
from iotile.sg.exceptions import SensorGraphSyntaxError
from iotile.sg import DataStream, SlotIdentifier
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
    assert parsed.asList()[0][0] == 60*60*24

    # Test block parsing
    parsed = language.block_bnf.parseString('every 1 day {}')
    assert parsed.asList()[0][0][0] == 60*60*24

    # Test stream parsing
    parsed = language.stream.parseString('output 1');
    assert isinstance(parsed.asList()[0], DataStream)

    # Test call_rpc statement
    parsed = language.callrpc_stmt.parseString(u'call 0x4001 on slot 1 => output 1;')
    assert parsed.asList()[0][0] == 0x4001

    # Test block with statement parsing
    parsed = language.block_bnf.parseString(u'every 1 day { call 0x5001 on slot 2 => output 1; }')
    assert parsed.asList()[0][0][0] == 60*60*24

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
    print(parser.dump_tree())
    assert False
