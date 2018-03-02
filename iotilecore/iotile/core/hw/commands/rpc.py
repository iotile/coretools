# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

from builtins import str
from .command import Command
import base64


class RPCCommand (Command):
    def __init__(self, address, feature, command, *args):
        """
        Create an RPC command
        """

        self.addr = int(address)
        self.feat = int(feature)
        self.cmd = int(command)
        self.spec = 0

        self.args = args
        self.result = ""

    def __str__(self):
        args = self._format_args()
        header = bytearray(4)
        header[0] = self.addr
        header[1] = self.feat
        header[2] = self.cmd
        header[3] = self.spec

        packet = header + args

        cmd = "binrpc %s" % base64.standard_b64encode(packet)
        return cmd

    def _convert_int(self, arg):
        out = bytearray(2)

        out[0] = arg & 0xFF
        out[1] = (arg & 0xFF00) >> 8;

        converted = out[0] | (out[1] << 8)

        if converted != arg:
            raise ValueError("Integer argument was too large to fit in an rpc 16 bit int: %d" % arg)

        return out

    def _pack_arg(self, arg):
        if isinstance(arg, int) or isinstance(arg, long):
            return self._convert_int(arg), False
        elif isinstance(arg, bytearray):
            return arg, True
        elif isinstance(arg, str):  # for python 3 compatibility, encode all newstr from future module
            return bytearray(arg.encode('utf-8')), True
        elif isinstance(arg, basestring):
            return bytearray(arg), True

        raise ValueError("Unknown argument type could not be converted for rpc call.")

    def _format_args(self):
        fmtd = bytearray()

        num_ints = 0
        num_bufs = 0

        for arg in self.args:
            a,is_buf = self._pack_arg(arg)
            fmtd += a

            if is_buf:
                num_bufs += 1
                buff_len = len(a)

            if not is_buf:
                if num_bufs != 0:
                    raise ValueError("Invalid rpc parameters, integer came after buffer.")

                num_ints += 1

        if num_bufs > 1:
            raise ValueError("You must pass at most 1 buffer. num_bufs=%d" % num_bufs)

        if len(fmtd) > 20:
            raise ValueError("Arguments are greater then the maximum mib packet size, size was %d" % len(fmtd))

        #Calculate the command type spec
        self.spec = len(fmtd)

        if len(fmtd) < 20:
            fmtd += bytearray(20 - len(fmtd))

        return fmtd
