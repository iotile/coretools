"""Basic virtual IOTile device class for testing tracing data from an IOTile device
"""

import binascii
from iotile.core.hw.virtual.virtualdevice import VirtualIOTileDevice, rpc, RPCInvalidIDError, RPCNotFoundError, TileNotFoundError

class TracingTestDevice(VirtualIOTileDevice):
    """Mock IOTileDevice that sends tracing data from the device

    If no arguments are passed, the fixed string 'Hello world, this is tracing data!'
    is sent over the tracing interface.

    Args:
        args (dict): Any arguments that you want to pass to create this device.
            Two mutually exclusive arguments are supported.

            If 'hex_data' is  present, it must be a hex string that is decoded
            into binary and then sent in 20 byte chunks over the tracing
            interface when it is opened.

            If 'ascii_data' is present, it must be an ascii string that is
            sent in 20 byte chunks with no decoding.

            If both keys are specified, ascii_data wins.

    """

    def __init__(self, args):
        iotile_id = args.get('iotile_id', 1)
        super(TracingTestDevice, self).__init__(iotile_id, 'Simple')

        data = bytearray("Hello world, this is tracing data!")

        if 'hex_data' in args:
            data = bytearray(binascii.unhexlify(args['hex_data']))

        if 'ascii_data' in args:
            data = bytearray(args['ascii_data'].encode('ascii'))

        # Create chunks of tracing data in 20 byte segments to simulate
        # what typically comes from real devices
        for i in xrange(0, len(data), 20):
            self.traces.append(data[i:i+20])

    @rpc(8, 0x0004, "", "H6sBBBB")
    def controller_name(self):
        """Return the name of the controller as a 6 byte string
        """

        status = (1 << 1) | (1 << 0)  # Configured and running

        return [0xFFFF, self.name, 1, 0, 0, status]
