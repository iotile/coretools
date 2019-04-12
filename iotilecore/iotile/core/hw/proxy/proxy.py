# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

# MIB Proxy Objects
from time import sleep
import struct
from iotile.core.hw.exceptions import RPCInvalidReturnValueError, BusyRPCResponse, RPCError, RPCInvalidArgumentsError, TileNotFoundError
from iotile.core.exceptions import HardwareError, ArgumentError
from iotile.core.utilities.typedargs import return_type, annotated, param, context
from ..virtual import pack_rpc_payload, unpack_rpc_payload


class TileBusProxyObject:
    def __init__(self, stream, address):
        self.stream = stream
        self.addr = address
        self._config_manager = ConfigManager(self)
        self._hwmanager = None

    @classmethod
    def ModuleName(cls):
        return 'NO APP'

    @annotated
    def config_manager(self):
        return self._config_manager

    def rpc(self, feature, cmd, *args, **kw):
        """Send an RPC call to this module, interpret the return value
        according to the result_type kw argument.  Unless raise keyword
        is passed with value False, raise an RPCException if the command
        is not successful.
        """

        rpc_id = (feature << 8 | cmd)

        result_format = _create_resp_format(kw.get('result_type'), kw.get('result_format'))
        arg_format = kw.get('arg_format')
        if arg_format is None:
            arg_format = _create_arg_format(args)

        passed_kw = {}
        if 'timeout' in kw:
            passed_kw['timeout'] = kw['timeout']

        response = self.rpc_v2(rpc_id, arg_format, result_format, *args, **passed_kw)

        old_return = kw.get('result_type')
        if old_return is not None:
            return _create_old_return_value(response, *old_return)

        return response

    def rpc_v2(self, cmd, arg_format, result_format, *args, **kw):
        """Send an RPC call to this module, interpret the return value
        according to the result_type kw argument.  Unless raise keyword
        is passed with value False, raise an RPCException if the command
        is not successful.

        v2 enforces the use of arg_format and result_format
        v2 combines the feature+cmd chunks in to a single 2-byte chunk
        """
        if args:
            packed_args = pack_rpc_payload(arg_format, list(args))
        elif arg_format == "":
            packed_args = b''
        else:
            raise RPCInvalidArgumentsError("Arg format expects arguments to be present", arg_format=arg_format, args=args)

        passed_kw = dict()
        if 'timeout' in kw:
            passed_kw['timeout'] = kw['timeout']

        try:
            should_retry = False
            payload = self.stream.send_rpc(self.addr, cmd, packed_args, **passed_kw)
        except BusyRPCResponse:
            if "retries" not in kw:
                kw['retries'] = 10

            # Sleep 100 ms and try again unless we've exhausted our retry attempts
            if kw["retries"] == 0:
                raise BusyRPCResponse("Could not complete RPC %d:%04X after 10 attempts due to busy tile" %
                                      (self.addr, cmd))

            should_retry = True

        # If the tile was busy, automatically retry up to 10 times
        if should_retry:
            kw['retries'] -= 1
            sleep(0.1)
            return self.rpc_v2(cmd, arg_format, result_format, *args, **kw)

        return unpack_rpc_payload(result_format, payload)

    @return_type("string")
    def hardware_version(self):
        """Return the embedded hardware version string for this tile.

        The hardware version is an up to 10 byte user readable string that is
        meant to encode any necessary information about the specific hardware
        that this tile is running on.  For example, if you have multiple
        assembly variants of a given tile, you could encode that information
        here.

        Returns:
            str: The hardware version read from the tile.
        """
        res = self.rpc(0x00, 0x02, result_type=(0, True))

        # Result is a string but with zero appended to the end to make it a fixed 10 byte size
        binary_version = res['buffer']

        ver = ""

        for x in binary_version:
            if x != 0:
                ver += chr(x)

        return ver

    @param("expected", "string", desc="The hardware string we expect to find")
    @return_type("bool")
    def check_hardware(self, expected):
        """Make sure the hardware version is what we expect.

        This convenience function is meant for ensuring that we are talking to
        a tile that has the correct hardware version.

        Args:
            expected (str): The expected hardware string that is compared
                against what is reported by the hardware_version RPC.

        Returns:
            bool: true if the hardware is the expected version, false otherwise
        """

        if len(expected) < 10:
            expected += '\0'*(10 - len(expected))

        err, = self.rpc(0x00, 0x03, expected, result_format="L")
        if err == 0:
            return True

        return False

    @return_type("basic_dict")
    def status(self):
        """Query the status of an IOTile including its name and version"""

        hw_type, name, major, minor, patch, status = self.rpc(0x00, 0x04, result_format="H6sBBBB")

        status = {
            'hw_type': hw_type,
            'name': name.decode('utf-8'),
            'version': (major, minor, patch),
            'status': status
        }

        return status

    @param("wait", "float", desc="Time to wait after reset for tile to boot up to a usable state")
    def reset(self, wait=1.0):
        """Immediately reset this tile."""
        try:
            self.rpc(0x00, 0x01)
        except TileNotFoundError:
            pass

        sleep(wait)

    @return_type("string")
    def tile_name(self):
        stat = self.status()

        return stat['name']

    @return_type("list(integer)", formatter="compact")
    def tile_version(self):
        stat = self.status()

        return stat['version']

    @return_type("map(string, bool)")
    def tile_status(self):
        """Get the current status of this tile"""
        stat = self.status()

        flags = stat['status']

        # FIXME: This needs to stay in sync with lib_common: cdb_status.h
        status = {}
        status['debug_mode'] = bool(flags & (1 << 3))
        status['configured'] = bool(flags & (1 << 1))
        status['app_running'] = bool(flags & (1 << 0))
        status['trapped'] = bool(flags & (1 << 2))

        return status


@context("ConfigManager")
class ConfigManager:
    """Manager Proxy for configuration variables on IOTiles

    Handles querying what config variables are defined, setting and getting
    their values.  Note that config variables should not change when application
    code is running so set_config_variables should not be called once an application
    is launched.

    Config variables should be thought of like environment variables in UNIX.  Each
    tile is conceptually a process and the config variables are the environment
    variables that are used to configure how that process runs.  They are captured
    when the process starts and should not change during process execution.

    Similarly, config variables are set on each tile by the TileBus controller every
    time the tile resets.  The tile can then read them to figure out how it should
    initialize itself.

    The variable cannot change value while the tile is running.  If you want to update
    a config variable, you need to stream that new value to the tile immediately after
    it resets before it passes control from its executive to its application firmware.

    This is usually not done manually but rather as part of the initialization process
    performed by the TileBus controller managing the IOTile Device.

    This ConfigManager is useful primarily for debugging, checking what values are actually
    set on a tile and what variables it supports.
    """

    def __init__(self, parent):
        self._proxy = parent

    @return_type('list(integer)')
    def list_variables(self):
        """List all of the configuration variables defined by this tile

        This function will tell you every configuration variable that this tile
        defines.  You can then query more information about a given variable
        using the returned 16 bit ids with the functions `describe_variable` and
        `get_variable`.

        Returns:
            list: A list of the ids of all of the config variables that are
            supported by this tile.
        """

        offset = 0
        ids = []

        while True:
            resp = self._proxy.rpc(0, 10, offset, result_type=(1, True))
            count = resp['ints'][0]

            if count == 0:
                break

            fmt = "<%dH" % count
            id_chuck = struct.unpack(fmt, resp['buffer'][:2*count])

            ids += id_chuck

            if count != 9:
                break

            offset += 9

        return ids

    @return_type("basic_dict")
    @param("d_id", "integer", desc="Variable ID to describe")
    def describe_variable(self, d_id):
        """Describe a configuration variable

        Queries metadata about a config variable directly from the tile where it
        is defined.  This information includes its size, where it is stored in RAM,
        and whether it has a fixed or variable length.

        The config variable is identified by its 16-bit numeric id that should match
        the value used to define the variable during the firmware build process in
        a .bus or .cdb file.

        Params:
            d_id (int): The 16 bit id of the config variable that we are trying to
                get information about.

        Returns:
            dict: A dict with information describing the config variable including
                its address in RAM, 16-bit id, maximum size and whether the variable
                is a fixed or variable size.
        """

        resp = self._proxy.rpc(0, 11, d_id, result_type=(2, True))

        err = resp['ints'][0]
        if err != 0:
            raise HardwareError("Error finding config variable by id", id=d_id, error_code=err)

        addr, d_id, flags = struct.unpack("<LHH", resp['buffer'])

        maxsize = (flags & ~(1 << 15)) & 0xFFFF
        variable_size = bool(flags >> 15)

        info = {
            'address': addr,
            'id': d_id,
            'max_size': maxsize,
            'variable_size': variable_size
        }

        return info

    @return_type("bytes", "repr")
    @param("d_id", "integer", desc="Variable ID to fetch")
    def get_variable(self, d_id):
        """Get value stored in a config variable

        Params:
            did (int): The 16 bit id of the config variable that we are trying to
                get the value of.

        Returns:
            bytearray: A raw byte array containing the binary data contained
                in this config variable.
        """

        offset = 0
        resp = self._proxy.rpc(0, 13, d_id, offset, result_type=(0, True))
        if len(resp['buffer']) == 0:
            return bytearray()

        retval = resp['buffer']

        while len(resp['buffer']) > 0:
            offset = len(retval)
            resp = self._proxy.rpc(0, 13, d_id, offset, result_type=(0, True))

            retval += resp['buffer']

        return retval

    @param("d_id", "integer", desc="Variable ID to set")
    @param("value", "bytes", desc="hexadecimal byte value to set")
    def set_variable(self, d_id, value):
        """Set the value stored in a config variable

        This function wraps the underlying RPC that is used internally in
        IOTile devices for the controller to update a tile's config variables
        every time the device resets.

        Since config variables are forbidden from changing while a tile is running,
        using this function directly is discouraged since it's unlikely you will
        calling it before the tile executive passes controller to its application.

        It is included here mainly for completeness and for advanced use cases
        where you need to directly set a config variable.

        Normally you should set config variables by adding an entry to the config
        database on the controller, which will then stream the data to the correct
        tile every time the tile resets and registers itself with the controller.

        Params:
            d_id (int): The 16 bit id of the config variable that we are trying to
                get the value of.
            value (bytearray): The data to store in the config variable
        """

        for offset in range(0, len(value), 16):
            remaining = len(value) - offset
            if remaining > 16:
                remaining = 16

            resp = self._proxy.rpc(0, 12, d_id, offset, value[offset:offset+remaining], result_type=(1, False))
            if resp['ints'][0] != 0:
                raise HardwareError("Error setting config variable", id=d_id, error_code=resp['ints'][0])


def _create_old_return_value(payload, num_ints, buff):
    """Parse the response of an RPC call into a dictionary with integer and buffer results"""

    parsed = {'ints': payload[:num_ints], 'buffer': None, 'error': 'No Error',
              'is_error': False, 'return_value': 0}

    if buff:
        parsed['buffer'] = bytearray(payload[-1])

    return parsed


def _create_resp_format(result_type, result_format):
    if result_type is not None and result_format is not None:
        raise ArgumentError("Both result_type and result_format specified",
                            result_format=result_format, result_type=result_type)

    if result_format is not None:
        return result_format

    if result_type is None:
        return ""

    try:
        int_count, has_buffer = result_type
    except ValueError as err:
        raise ArgumentError("Invalid value for result_type, must be tuple(int_count, has_buffer)",
                            result_type=result_type) from err

    if has_buffer is False and int_count == 0:
        return ""

    if has_buffer is False:
        return "%dH" % int_count

    return "%dHV" % int_count


def _create_arg_format(args):
    if len(args) == 0:
        return ""

    int_count = len(args)
    has_buffer = False

    if isinstance(args[-1], (bytes, bytearray)):
        int_count = int_count - 1
        has_buffer = True

    arg_code = ""

    if int_count > 0:
        arg_code += "%dH" % int_count

    if has_buffer:
        arg_code += "V"

    return arg_code
