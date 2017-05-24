"""Globally available processing functions that can be used in sensor graph nodes.

These functions should not be used directly but rather will be invoked by name
when creating a sensor graph node inside the SensorGraph class.  They are found
by looking at the installed python packages using pkg_resources.
"""

from iotile.core.exceptions import HardwareError
from iotile.sg import StreamEmptyError
from iotile.core.hw.reports import IOTileReading


def copy_all_a(input_a, *other_inputs, **kwargs):
    """Copy all readings in input a into the output.

    All other inputs are skipped so that after this function
    runs there are no readings left in any of the input walkers
    when the function finishes, even if it generated no output
    readings.
    """

    output = []
    while input_a.count() > 0:
        output.append(input_a.pop())

    for input_x in other_inputs:
        input_x.skip_all()

    return output

def call_rpc(*inputs, **kwargs):
    """Call an RPC based on the encoded value read from input b.

    The response of the RPC must be a 4 byte value that is used as
    the output of this call.  The encoded RPC must be a 32 bit value
    encoded as "BBH":
        B: ignored, should be 0
        B: the address of the tile that we should call
        H: The id of the RPC to call

    All other readings are then skipped so that there are no
    readings in any input queue when this function returns
    """

    rpc_executor = kwargs['rpc_executor']

    output = []
    try:
        value = inputs[1].pop()

        addr = value.value >> 16
        rpc_id = value.value & 0xFFFF

        reading_value = rpc_executor.rpc(addr, rpc_id)
        output.append(IOTileReading(0, 0, output))
    except (HardwareError, StreamEmptyError):
        pass

    for input_x in inputs:
        input_x.skip_all()

    return output
