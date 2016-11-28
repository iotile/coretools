# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from command import Command
from iotile.core.hw.exceptions import *
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

    #FIXME: Update these to correspond with the new error codes
    def parse_result(self, num_ints, buff):
        parsed = {'ints':[], 'buffer':"", 'error': 'No Error', 'is_error': False}

        status_code = self.status
        complete_status = self.complete_status & 0b01111111

        #Check for a command stream layer error
        if self.complete_status == 254:
            parsed['error'] = self.result
            parsed['status'] = self.complete_status
            parsed['is_error'] = True

            return parsed

        parsed['status'] = complete_status

        #Check if the module was not found
        if self.complete_status == 0xFF:
            parsed['error'] = 'Module at address ' + str(self.addr) + ' not found.'
            parsed['is_error'] = True
            return parsed

        #Check for protocol defined errors
        if not complete_status & (1<<6):
            #This is a protocol defined error since the App Defined bit is not set
            if status_code == 0:
                parsed['error'] = 'Module Busy'
            elif status_code == 1:
                parsed['error'] = 'Checksum Error'
            elif status_code == 2:
                parsed['error'] = 'Unsupported Command'
            else:
                parsed['error'] = 'Unrecognized MIB status code'

            parsed['is_error'] = True
            return parsed

        #Otherwise, parse the results according to the type information given
        size = len(self.result)

        if size < 2*num_ints:
            raise RPCException(300, 'Return value too short to unpack : %s' % self.result)
        elif buff == False and size != 2*num_ints:
            raise RPCException(301, 'Return value does not match return type: %s' % self.result)

        for i in xrange(0, num_ints):
            low = ord(self.result[2*i])
            high = ord(self.result[2*i + 1])
            parsed['ints'].append((high << 8) | low)

        if buff:
            parsed['buffer'] = self.result[2*num_ints:]

        return parsed
