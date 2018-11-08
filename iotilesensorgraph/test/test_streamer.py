"""Tests of DataStreamer functionality."""

from iotile.sg.streamer_descriptor import parse_binary_descriptor, parse_string_descriptor, create_binary_descriptor


def test_descriptors():
    """Make sure we can parse string and binary descriptors."""
    streamer = parse_string_descriptor('manual realtime streamer on unbuffered 1 to controller')
    assert str(streamer) == 'manual realtime streamer on unbuffered 1'

    bin_desc = create_binary_descriptor(streamer)
    streamer2 = parse_binary_descriptor(bin_desc)

    assert streamer2 == streamer

    streamer = parse_string_descriptor('realtime streamer on unbuffered 1 to slot 5 with streamer 0')
    assert str(streamer) == 'manual realtime streamer on unbuffered 1 to slot 5 with streamer 0'

    streamer = parse_string_descriptor(u'realtime streamer on unbuffered 1 to slot 5 with streamer 0')
    assert str(streamer) == 'manual realtime streamer on unbuffered 1 to slot 5 with streamer 0'

    bin_desc = create_binary_descriptor(streamer)
    streamer2 = parse_binary_descriptor(bin_desc)

    assert streamer2 == streamer
