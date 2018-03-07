import os.path
import binascii
from iotile.sg.output_formats import format_script

def compare_binary_data(data, reference_file):
    """Compare binary data with a reference file."""

    in_path = os.path.join(os.path.dirname(__file__), 'reference_output', reference_file)

    with open(in_path, "rb") as in_file:
        ref_data = in_file.read()

    print("Data: %s" % binascii.hexlify(data[:32]))
    print("Ref : %s" % binascii.hexlify(ref_data[:32]))

    assert data == bytearray(ref_data)


def test_script_output_format(usertick_gate_opt):
    """Make sure the output script format works."""

    sg = usertick_gate_opt

    output = format_script(sg)
    compare_binary_data(output, 'usertick_optimized_script.trub')
