import os.path
import binascii
from iotile.sg.output_formats import format_script, format_snippet, format_config, format_ascii

def compare_binary_data(data, reference_file):
    """Compare binary data with a reference file."""

    in_path = os.path.join(os.path.dirname(__file__), 'reference_output', reference_file)

    with open(in_path, "rb") as in_file:
        ref_data = in_file.read()

    assert data == bytearray(ref_data)


def compare_string_data(data, reference_file):
    """Compare utf-8 data with a reference file."""

    in_path = os.path.join(os.path.dirname(__file__), 'reference_output', reference_file)

    with open(in_path, "rb") as in_file:
        ref_data = in_file.read().decode('utf-8')

    # Don't compare EOL separators so we can store reference files on
    # one platform and use them on another.
    data_lines = data.splitlines()
    ref_lines = ref_data.splitlines()

    assert data_lines == ref_lines


def test_script_output_format(usertick_gate_opt, streamer_types):
    """Make sure the output script format works."""

    output = format_script(usertick_gate_opt)
    streamer_out = format_script(streamer_types)

    compare_binary_data(output, 'usertick_optimized_script.trub')
    compare_binary_data(streamer_out, 'streamers_script.trub')


def test_snippet_output_format(usertick_gate_opt, streamer_types):
    """Make sure the snippet output format works."""

    snippet = format_snippet(usertick_gate_opt)
    streamer_snippet = format_snippet(streamer_types)

    compare_string_data(snippet, 'usertick_optimized_snippet.txt')
    compare_string_data(streamer_snippet, 'streamers_snippet.txt')


def test_config_output_format(usertick_gate_opt):
    """Make sure the config output format works."""

    config = format_config(usertick_gate_opt)
    compare_string_data(config, 'usertick_optimized_config.txt')


def test_ascii_output_format(usertick_gate_opt, streamer_types):
    """Make sure the ascii output format works."""

    ascii_txt = format_ascii(usertick_gate_opt)
    streamer_ascii = format_ascii(streamer_types)
    compare_string_data(ascii_txt, 'usertick_optimized_ascii.txt')
    compare_string_data(streamer_ascii, 'streamers_ascii.txt')
