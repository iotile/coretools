import os.path
import binascii
from iotile.sg.output_formats import format_script, format_snippet, format_config, format_ascii

def compare_binary_data(data, reference_file):
    """Compare binary data with a reference file."""

    in_path = os.path.join(os.path.dirname(__file__), 'reference_output', reference_file)

    with open(in_path, "rb") as in_file:
        ref_data = in_file.read()

    assert data == bytearray(ref_data)


def test_script_output_format(usertick_gate_opt):
    """Make sure the output script format works."""

    sg = usertick_gate_opt

    output = format_script(sg)

    compare_binary_data(output, 'usertick_optimized_script.trub')


def test_snippet_output_format(usertick_gate_opt):
    """Make sure the snippet output format works."""

    snippet = format_snippet(usertick_gate_opt)


def test_config_output_format(usertick_gate_opt):
    """Make sure the config output format works."""

    config = format_config(usertick_gate_opt)


def test_ascii_output_format(usertick_gate_opt):
    """Make sure the ascii output format works."""

    config = format_ascii(usertick_gate_opt)
