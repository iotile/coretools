"""Tests for DataStream objects."""

from builtins import str
from iotile.sg import DataStream, DataStreamSelector


def test_stream_type_parsing():
    """Make sure we can parse each type of stream."""

    # Make sure parsing stream type works
    stream = DataStream.FromString('buffered 1')
    assert stream.stream_type == stream.BufferedType
    stream = DataStream.FromString(u'buffered 1')
    assert stream.stream_type == stream.BufferedType

    stream = DataStream.FromString('unbuffered 1')
    assert stream.stream_type == stream.UnbufferedType
    stream = DataStream.FromString(u'unbuffered 1')
    assert stream.stream_type == stream.UnbufferedType

    stream = DataStream.FromString('counter 1')
    assert stream.stream_type == stream.CounterType
    stream = DataStream.FromString(u'counter 1')
    assert stream.stream_type == stream.CounterType

    stream = DataStream.FromString('constant 1')
    assert stream.stream_type == stream.ConstantType
    stream = DataStream.FromString(u'constant 1')
    assert stream.stream_type == stream.ConstantType

    stream = DataStream.FromString('output 1')
    assert stream.stream_type == stream.OutputType
    stream = DataStream.FromString(u'output 1')
    assert stream.stream_type == stream.OutputType


def test_stream_id_parsing():
    """Make sure we can parse stream ids."""

    stream = DataStream.FromString('buffered 1')
    assert stream.stream_id == 1

    stream = DataStream.FromString('buffered 0x100')
    assert stream.stream_id == 0x100

    stream = DataStream.FromString(u'buffered 1')
    assert stream.stream_id == 1

    stream = DataStream.FromString(u'buffered 0x100')
    assert stream.stream_id == 0x100


def test_system_parsing():
    """Make sure we can parse the system prefix."""

    stream = DataStream.FromString('buffered 1')
    assert stream.system is False
    stream = DataStream.FromString(u'buffered 1')
    assert stream.system is False

    stream = DataStream.FromString('system buffered 1')
    assert stream.system is True
    stream = DataStream.FromString(u'system buffered 1')
    assert stream.system is True


def test_stringification():
    """Make sure we can stringify DataStream objects."""

    stream1 = DataStream.FromString('system buffered 1')
    stream2 = DataStream.FromString('buffered 0xF')

    assert str(stream1) == str('system buffered 1')
    assert str(stream2) == str('buffered 15')


def test_selector_parsing():
    """Make sure we can parse DataStreamSelector strings."""

    # Make sure parsing stream type works
    stream = DataStreamSelector.FromString('buffered 1')
    assert stream.match_type == DataStream.BufferedType
    stream = DataStreamSelector.FromString(u'buffered 1')
    assert stream.match_type == DataStream.BufferedType

    stream = DataStreamSelector.FromString('unbuffered 1')
    assert stream.match_type == DataStream.UnbufferedType
    stream = DataStreamSelector.FromString(u'unbuffered 1')
    assert stream.match_type == DataStream.UnbufferedType

    stream = DataStreamSelector.FromString('counter 1')
    assert stream.match_type == DataStream.CounterType
    stream = DataStreamSelector.FromString(u'counter 1')
    assert stream.match_type == DataStream.CounterType

    stream = DataStreamSelector.FromString('constant 1')
    assert stream.match_type == DataStream.ConstantType
    stream = DataStreamSelector.FromString(u'constant 1')
    assert stream.match_type == DataStream.ConstantType

    stream = DataStreamSelector.FromString('output 1')
    assert stream.match_type == DataStream.OutputType
    stream = DataStreamSelector.FromString(u'output 1')
    assert stream.match_type == DataStream.OutputType


def test_stream_selector_id_parsing():
    """Make sure we can parse stream ids."""

    stream = DataStreamSelector.FromString('buffered 1')
    assert stream.match_id == 1
    assert stream.match_spec == DataStreamSelector.MatchUserOnly

    stream = DataStreamSelector.FromString('buffered 0x100')
    assert stream.match_id == 0x100
    assert stream.match_spec == DataStreamSelector.MatchUserOnly

    stream = DataStreamSelector.FromString(u'buffered 1')
    assert stream.match_id == 1
    assert stream.match_spec == DataStreamSelector.MatchUserOnly

    stream = DataStreamSelector.FromString(u'buffered 0x100')
    assert stream.match_id == 0x100
    assert stream.match_spec == DataStreamSelector.MatchUserOnly

    stream = DataStreamSelector.FromString(u'system buffered 0x100')
    assert stream.match_id == 0x100
    assert stream.match_spec == DataStreamSelector.MatchSystemOnly

    stream = DataStreamSelector.FromString(u'all buffered')
    assert stream.match_id is None
    assert stream.match_spec == DataStreamSelector.MatchUserAndBreaks

    stream = DataStreamSelector.FromString(u'all user buffered')
    assert stream.match_id is None
    assert stream.match_spec == DataStreamSelector.MatchUserOnly

    stream = DataStreamSelector.FromString(u'all combined buffered')
    assert stream.match_id is None
    assert stream.match_spec == DataStreamSelector.MatchCombined

    stream = DataStreamSelector.FromString(u'all system buffered')
    assert stream.match_id is None
    assert stream.match_spec == DataStreamSelector.MatchSystemOnly


def test_matching():
    """Test selector stream matching."""

    sel = DataStreamSelector.FromString(u'all system buffered')
    assert sel.matches(DataStream.FromString('system buffered 1'))
    assert not sel.matches(DataStream.FromString('buffered 1'))
    assert not sel.matches(DataStream.FromString('counter 1'))

    sel = DataStreamSelector.FromString(u'all user outputs')
    assert sel.matches(DataStream.FromString('output 1'))
    assert not sel.matches(DataStream.FromString('system output 1'))
    assert not sel.matches(DataStream.FromString('counter 1'))

    sel = DataStreamSelector.FromString(u'all combined outputs')
    assert sel.matches(DataStream.FromString('output 1'))
    assert sel.matches(DataStream.FromString('system output 1'))
    assert not sel.matches(DataStream.FromString('counter 1'))

    sel = DataStreamSelector.FromString(u'all outputs')
    assert sel.matches(DataStream.FromString('output 1'))
    assert sel.matches(DataStream.FromString('system output 1024'))
    assert not sel.matches(DataStream.FromString('system output 1'))
    assert not sel.matches(DataStream.FromString('counter 1'))


def test_encoding():
    """Test data stream and selector encoding."""

    sel = DataStreamSelector.FromString(u'all system output')
    assert sel.encode() == 0x5FFF

    sel = DataStreamSelector.FromString(u'all user output')
    assert sel.encode() == 0x57FF

    sel = DataStreamSelector.FromString(u'all output')
    assert sel.encode() == 0xD7FF

    sel = DataStreamSelector.FromString(u'all combined output')
    assert sel.encode() == 0xDFFF

    stream = DataStream.FromString('output 1')
    assert stream.encode() == 0x5001

    stream = DataStream.FromString('unbuffered 10')
    assert stream.encode() == 0x100a


def test_selector_from_encoded():
    """Make sure we can create a selector from an encoded value."""

    sel = DataStreamSelector.FromEncoded(0x5FFF)
    assert str(sel) == 'all system outputs'

    sel = DataStreamSelector.FromEncoded(0xD7FF)
    assert str(sel) == 'all outputs'

    sel = DataStreamSelector.FromEncoded(0x100a)
    assert str(sel) == 'unbuffered 10'

    assert str(DataStreamSelector.FromEncoded(DataStreamSelector.FromString('all combined output').encode())) == 'all combined outputs'


def test_buffered_pluralization():
    """Make sure we don't incorrectly pluralize buffered streams."""

    sel = DataStreamSelector.FromString('all buffered')
    assert str(sel) == 'all buffered'
