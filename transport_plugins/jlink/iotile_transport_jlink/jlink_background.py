"""A background thread for asynchronous operations on the jlink adapter."""

import threading
import logging
import struct
import time
from collections import namedtuple
from time import monotonic
from iotile.core.exceptions import ArgumentError, HardwareError
import iotile_transport_jlink.devices as devices
from .structures import ControlStructure

from queue import Queue

# pylint:disable=invalid-name;This is not a constant so its name is okay
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

JLinkCommand = namedtuple("JLinkCommand", ['name', 'args', 'callback'])


class JLinkControlThread(threading.Thread):
    """A class that synchronously executes long-running commands on a jlink.

    Args:
        jlink (pylink.JLink): An open jlink adapter instance.
    """

    STOP = 0
    READ_MEMORY = 1
    FIND_CONTROL = 2
    VERIFY_CONTROL = 3
    SEND_RPC = 4
    DUMP_ALL_RAM = 5
    PROGRAM_FLASH = 6
    SEND_SCRIPT = 7

    KNOWN_COMMANDS = {
        STOP: None,
        READ_MEMORY: "_read_memory",
        FIND_CONTROL: "_find_control_structure",
        VERIFY_CONTROL: "_verify_control_structure",  # Takes device_info, (optional) control_info parameters
        SEND_RPC: "_send_rpc",  # Takes control_info, address, rpc_id, payload, poll_interval, timeout
        SEND_SCRIPT: "_send_script",  # Takes  device_info, control_info, script, progress_callback

        # Debug commands
        DUMP_ALL_RAM: "_dump_all_ram",  # Takes device_info, control_info (ignored), args (ignored)
        PROGRAM_FLASH: "_program_flash" # Takes device_info, control_info (ignored), args {'data': binary}
    }

    def __init__(self, jlink):
        super(JLinkControlThread, self).__init__()

        self._jlink = jlink
        self._commands = Queue()

    def run(self):
        logger.critical("Starting JLink control thread")
        while True:
            try:
                cmd = self._commands.get()
                if not isinstance(cmd, JLinkCommand):
                    logger.error("Invalid command object that is not a JLinkCommand: %s", cmd)
                    continue

                if cmd.name == JLinkControlThread.STOP:
                    logger.info("stop command received")
                    break

                callback = cmd.callback
                exception = None
                result = None
                try:
                    funcname = self.KNOWN_COMMANDS.get(cmd.name)
                    if funcname is None:
                        raise ArgumentError("Unknown command name in JLinkControlThread", name=cmd.name)

                    func = getattr(self, funcname)

                    args = cmd.args
                    if args is None:
                        args = ()

                    result = func(*args)
                except Exception as exc:  #pylint:disable=broad-except;We want to rethrow everything in the main thread
                    exception = exc
                    logger.exception("Error executing command %s with args %s", cmd.name, cmd.args)

                if callback is not None:
                    callback(cmd.name, result, exception=exception)
            except:  #pylint:disable=bare-except;We want to keep our control thread always open
                logger.exception("Uncaught exception in JLink control thread")

        logger.critical("Shutting down JLink control thread")

    def command(self, cmd_name, callback, *args):
        """Run an asynchronous command.

        Args:
            cmd_name (int): The unique code for the command to execute.
            callback (callable): The optional callback to run when the command finishes.
                The signature should be callback(cmd_name, result, exception)
            *args: Any arguments that are passed to the underlying command handler
        """
        cmd = JLinkCommand(cmd_name, args, callback)
        self._commands.put(cmd)

    def stop(self):
        """Tell this thread to stop, do not wait for it to finish."""
        self._commands.put(JLinkCommand(JLinkControlThread.STOP, None, None))

    def _send_rpc(self, device_info, control_info, address, rpc_id, payload, poll_interval, timeout):
        """Write and trigger an RPC."""

        write_address, write_data = control_info.format_rpc(address, rpc_id, payload)
        self._jlink.memory_write32(write_address, write_data)

        self._trigger_rpc(device_info)

        start = monotonic()
        now = start

        poll_address, poll_mask = control_info.poll_info()

        while (now - start) < timeout:
            time.sleep(poll_interval)
            value, = self._jlink.memory_read8(poll_address, 1)

            if value & poll_mask:
                break

            now = monotonic()

        if (now - start) >= timeout:
            raise HardwareError("Timeout waiting for RPC response", timeout=timeout, poll_interval=poll_interval)

        read_address, read_length = control_info.response_info()
        read_data = self._read_memory(read_address, read_length, join=True)

        return control_info.format_response(read_data)

    def _send_script(self, device_info, control_info, script, progress_callback):
        """Send a script by repeatedly sending it as a bunch of RPCs.

        This function doesn't do anything special, it just sends a bunch of RPCs
        with each chunk of the script until it's finished.
        """

        for i in range(0, len(script), 20):
            chunk = script[i:i+20]
            self._send_rpc(device_info, control_info, 8, 0x2101, chunk, 0.001, 1.0)
            if progress_callback is not None:
                progress_callback(i + len(chunk), len(script))

    def _trigger_rpc(self, device_info):
        """Trigger an RPC in a device specific way."""

        method = device_info.rpc_trigger
        if isinstance(method, devices.RPCTriggerViaSWI):
            self._jlink.memory_write32(method.register, [1 << method.bit])
        else:
            raise HardwareError("Unknown RPC trigger method", method=method)

    def _dump_all_ram(self, device_info, _control_info, _args, _progress_callback):
        memory = self._read_memory(device_info.ram_start, device_info.ram_size)
        return memory

    def _program_flash(self, _device_info, _control_info, args, progress_callback):
        base_address = args.get('base_address')
        data = args.get('data')

        if base_address is None or data is None:
            raise ArgumentError("Invalid arguments to program flash, expected a dict with base_address and data members")

        def _internal_progress(action, _prog_string, percent):
            """Convert jlink progress callback into our own (finished, total) format."""
            action_table = {'Compare': 1, 'Erase': 2,
                            'Flash': 3, 'Verify': 4}

            if progress_callback is not None:
                progress_callback(action_table.get(action, 4)*percent, 400)

        logger.info("Flashing %d bytes starting at address 0x%08X", len(data), base_address)
        self._jlink.flash(data, base_address, _internal_progress)
        self._jlink.reset(halt=False)

    def _read_memory(self, start_address, length, chunk_size=4, join=True):
        if chunk_size not in (1, 2, 4):
            raise ArgumentError("Invalid chunk size specified in read_memory command", chunk_size=chunk_size)

        if length % chunk_size != 0:
            raise ArgumentError("You must specify a length that is an integer multiple of chunk_size", length=length, chunk_size=chunk_size)

        if start_address % chunk_size != 0:
            raise ArgumentError("You must specify a start address that is aligned to your chunk_size", start_address=start_address, chunk_size=chunk_size)

        word_length = length // chunk_size
        if chunk_size == 1:
            words = self._jlink.memory_read8(start_address, word_length)
            pack_size = "B"
        elif chunk_size == 2:
            words = self._jlink.memory_read16(start_address, word_length)
            pack_size = "H"
        elif chunk_size == 4:
            words = self._jlink.memory_read32(start_address, word_length)
            pack_size = "L"

        if join:
            return struct.pack("<%d%s" % (word_length, pack_size), *words)

        return words

    def _find_control_structure(self, start_address, search_length):
        """Find the control structure in RAM for this device.

        Returns:
            ControlStructure: The decoded contents of the shared memory control structure
                used for communication with this IOTile device.
        """

        words = self._read_memory(start_address, search_length, chunk_size=4, join=False)
        found_offset = None

        for i, word in enumerate(words):
            if word == ControlStructure.CONTROL_MAGIC_1:
                if (len(words) - i) < 4:
                    continue

                if words[i + 1] == ControlStructure.CONTROL_MAGIC_2 and words[i + 2] == ControlStructure.CONTROL_MAGIC_3 and words[i + 3] == ControlStructure.CONTROL_MAGIC_4:
                    found_offset = i
                    break

        if found_offset is None:
            raise HardwareError("Could not find control structure magic value in search area")

        struct_info = words[found_offset + 4]
        _version, _flags, length = struct.unpack("<BBH", struct.pack("<L", struct_info))

        if length % 4 != 0:
            raise HardwareError("Invalid control structure length that was not a multiple of 4", length=length)

        word_length = length // 4
        control_data = struct.pack("<%dL" % word_length, *words[found_offset:found_offset + word_length])

        logger.info("Found control stucture at address 0x%08X, word_length=%d", start_address + 4*found_offset, word_length)

        return ControlStructure(start_address + 4*found_offset, control_data)

    def _verify_control_structure(self, device_info, control_info=None):
        """Verify that a control structure is still valid or find one.

        Returns:
            ControlStructure: The verified or discovered control structure.
        """

        if control_info is None:
            control_info = self._find_control_structure(device_info.ram_start, device_info.ram_size)

        #FIXME: Actually reread the memory here to verify that the control structure is still valid
        return control_info

