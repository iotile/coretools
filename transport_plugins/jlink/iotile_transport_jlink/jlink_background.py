"""A class with async wrappers around operations on the jlink adapter."""

import asyncio
import logging
import struct
import time
import pylink
from iotile.core.exceptions import ArgumentError, HardwareError
from iotile.core.utilities import SharedLoop
import iotile_transport_jlink.devices as devices
from .structures import ControlStructure
from .data import flash_forensics_config as ff_cfg


# pylint:disable=invalid-name;This is not a constant so its name is okay
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class AsyncJLink:
    """A class that wraps long-running commands on a jlink into async functions.

    Args:
        jlink (pylink.JLink): An open jlink adapter instance.
    """

    def __init__(self, jlink_adapter, loop=SharedLoop):
        self._jlink_adapter = jlink_adapter
        self._jlink = None
        self._loop = loop

        # maintenance can be enabled for different interfaces
        self._maintenance_counter = 0
        self._maintenance_task = None
        self.rpc_response_event = self._loop.create_event() # triggered when the controller acknowledge rpc response

    async def send_rpc(self, device_info, control_info, address, rpc_id, payload, timeout):
        """Write and trigger an RPC."""

        write_address, write_data = control_info.format_rpc(address, rpc_id, payload)
        await self.write_memory(write_address, write_data, chunk_size=4)

        await self._trigger_rpc(device_info)
        await self._wait_rpc_completion(control_info, timeout)

        read_address, read_length = control_info.response_info()
        read_data = await self.read_memory(read_address, read_length, join=True)

        return control_info.format_response(read_data)

    async def send_script(self, device_info, control_info, script):
        """Send a script by repeatedly sending it as a bunch of RPCs.

        This function doesn't do anything special, it just sends a bunch of RPCs
        with each chunk of the script until it's finished.
        """

        conn_string = self._jlink_adapter._get_property(self._jlink_adapter._connection_id, 'connection_string')
        for i in range(0, len(script), 20):
            chunk = script[i:i+20]
            await self.send_rpc(device_info, control_info, 8, 0x2101, chunk, 1.0)

            event = {
                "operation": "script",
                "finished": i + len(chunk),
                "total": len(script)
            }
            self._jlink_adapter.notify_event(conn_string, 'progress', event)

    async def _wait_rpc_completion(self, control_info, timeout):
        try:
            await asyncio.wait_for(self.rpc_response_event.wait(), timeout)
        except asyncio.TimeoutError:
            raise HardwareError("Timeout waiting for RPC response", timeout=timeout)

        poll_address, poll_mask = control_info.poll_info()
        value, = await self.read_memory(poll_address, 1, chunk_size=1)

        if not value & poll_mask:
            raise HardwareError("RPC complete bit is not set")

    async def _trigger_rpc(self, device_info):
        """Trigger an RPC in a device specific way."""
        self.rpc_response_event.clear()

        method = device_info.rpc_trigger
        if isinstance(method, devices.RPCTriggerViaSWI):
            await self.write_memory(method.register, [1 << method.bit], chunk_size=4)
        else:
            raise HardwareError("Unknown RPC trigger method", method=method)

    def _continue_blocking(self):
        self._jlink.step()
        self._jlink._dll.JLINKARM_Go()
        while not self._jlink.halted():
            time.sleep(0.01)

    async def _continue(self):
        await self._loop.run_in_executor(self._continue_blocking)

    async def _inject_blob(self, absolute_path_to_binary):
        with open(absolute_path_to_binary, mode='rb', loop=self._loop) as ff_file:
            ff_bin = await self._loop.run_in_executor(ff_file.read())
        await self.write_memory(ff_cfg.ff_addresses['blob_inject_start'], ff_bin, chunk_size=1)

    def _update_reg_blocking(self, register, value):
        if not self._jlink.halted():
            self._jlink.halt()
        self._jlink.register_write(register, value)

    def _get_register_handle_blocking(self, register_string):
        reg_list = self._jlink.register_list()
        reg_str_paren = '(' + register_string + ')'

        for reg in reg_list:
            reg_name = self._jlink.register_name(reg)
            if reg_name is register_string or reg_str_paren in reg_name:
                return reg
        return None

    async def _get_ff_max_read_length(self):
        max_read_length, = await self.read_memory(
            ff_cfg.ff_addresses['max_read_length'], 1, chunk_size=2)
        return max_read_length

    async def _write_ff_dump_cmd(self, start, length):
        start_bytes = start.to_bytes(4, byteorder='little')
        length_bytes = length.to_bytes(2, byteorder='little')

        await self.write_memory(ff_cfg.ff_addresses['read_command_address'], start_bytes, chunk_size=1)
        written_start, = await self.read_memory(ff_cfg.ff_addresses['read_command_address'], 1, chunk_size=4)

        if written_start != start:
            raise ArgumentError("FF dump command address was not successfully written.")
        else:
            logger.info("FF dump command address written to %s", hex(start))

        await self.write_memory(ff_cfg.ff_addresses['read_command_length'], length_bytes, chunk_size=1)
        written_length, = await self.read_memory(ff_cfg.ff_addresses['read_command_length'], 1, chunk_size=2)

        if written_length != length:
            raise ArgumentError("ff dump command length was not successfully written.")
        else:
            logger.info("ff dump command length written to %d", length)

    async def _read_ff_dump_resp(self, length):
        buffer_addr, = await self._jlink.read_memory(ff_cfg.ff_addresses['read_response_buffer_address'], 1)
        logger.info("Response buffer at %s", hex(buffer_addr))
        flash_dump = await self.read_memory(buffer_addr, length)
        return flash_dump

    async def _read_mapped_memory(self, device_info, region, read_start_addr, read_length):
        if read_length is None:
            if region == 'ram':
                memory = await self.read_memory(device_info.ram_start, device_info.ram_size)
            elif region == 'flash':
                memory = await self.read_memory(device_info.flash_start, device_info.flash_size)
            elif region == 'mapped':
                raise ArgumentError("Must specify a data length to read from mapped memory.")
        else:
            if region == 'ram':
                if read_length > device_info.ram_size:
                    raise ArgumentError("Data length must be less than RAM size.", ram_size=device_info.ram_size)
                if read_start_addr > device_info.ram_size:
                    raise ArgumentError("Starting address must be less than RAM size.", ram_size=device_info.ram_size)
                memory = await self.read_memory(read_start_addr + device_info.ram_start, read_length)

            elif region == 'flash':
                if read_length > device_info.flash_size:
                    raise ArgumentError("Data length must be less than flash size.", flash_size=device_info.flash_size)
                if read_start_addr > device_info.flash_size:
                    raise ArgumentError("Starting address must be less than flash size.", flash_size=device_info.flash_size)
                memory = await self.read_memory(read_start_addr + device_info.flash_start, read_length)

            elif region == 'mapped':
                if read_start_addr > 0:
                    memory = await self.read_memory(read_start_addr, read_length)
                else:
                    raise ArgumentError("Invalid start address to read from mapped memory.")

        return memory

    async def debug_read_memory(self, device_info, _control_info, args):
        memory_region = args.get('region').lower()
        start_addr    = args.get('start')
        data_length   = args.get('length')
        pause         = args.get('halt')

        if memory_region == 'external':
            if pause is False:
                raise ArgumentError("Pause must be True in order to read external data.")
            await self.reset()
            await self._inject_blob(ff_cfg.ff_absolute_bin_path)

            pc_reg = await self._loop.run_in_executor(
                self._get_register_handle_blocking, "PC")
            await self._loop.run_in_executor(self._update_reg_blocking,
                pc_reg, ff_cfg.ff_addresses['program_start'])

            await self._continue()
            max_read_length = await self._get_ff_max_read_length()

            bytes_dumped = 0
            memory = b''
            while bytes_dumped < data_length:
                bytes_to_dump = max_read_length if (data_length - bytes_dumped) > max_read_length else (data_length - bytes_dumped)

                logger.info("BKPT hit, writing SPI dump command now...")

                logger.info("At PC: %s", hex(await self.register_read(pc_reg)))
                await self._write_ff_dump_cmd(start_addr, data_length)

                await self._continue()

                logger.info("BKPT hit, reading response buffer address...")
                logger.info("At PC: %s", hex(await self.register_read(pc_reg)))
                memory += await self._read_ff_dump_resp(data_length)

                bytes_dumped += bytes_to_dump
                await self._continue()

            await self.reset()
            await self._loop.run_in_executor(self._jlink._dll.JLINKARM_Go)

        elif memory_region == 'flash' or memory_region == 'ram' or memory_region == 'mapped':
            if pause is True:
                await self._loop.run_in_executor(self._jlink.halt)

            memory = await self._read_mapped_memory(device_info, memory_region, start_addr, data_length)

            if pause is True:
                await self._loop.run_in_executor(self._jlink._dll.JLINKARM_Go)
        else:
            raise ArgumentError("Invalid memory region specified, must be one of ['flash', 'ram', 'external', 'mapped']")

        return memory

    async def debug_write_memory(self, _device_info, _control_info, args):
        memory_region = args.get('region').lower()

        if memory_region == 'external' or memory_region == 'flash':
            raise ArgumentError("Writing to flash/external is not currently supported.")
        await self.write_memory(args.get('address'), args.get('data'), raw_data=True)

    async def program_flash(self, _device_info, _control_info, args):
        base_address = args.get('base_address')
        data = args.get('data')

        if base_address is None or data is None:
            raise ArgumentError("Invalid arguments to program flash, expected a dict with base_address and data members")

        conn_string = self._jlink_adapter._get_property(self._jlink_adapter._connection_id, 'connection_string')

        def _internal_progress(action, _prog_string, percent):
            """Convert jlink progress callback into our own (finished, total) format."""
            action_table = {'Compare': 0, 'Erase': 1,
                            'Flash': 2, 'Verify': 3}

            event = {
                "operation": "debug",
                "finished": action_table.get(action, 3) * 100 + percent,
                "total": 400
            }
            self._jlink_adapter.notify_event(conn_string, 'progress', event)

        logger.info("Flashing %d bytes starting at address 0x%08X", len(data), base_address)
        await self._loop.run_in_executor(
            self._jlink.flash, data, base_address, _internal_progress)
        await self.reset(halt=False)

    @staticmethod
    def _connect_jlink_blocking(jlink_serial, jlink_name):
        jlink = pylink.JLink()
        jlink.open(jlink_serial)
        jlink.set_tif(pylink.enums.JLinkInterfaces.SWD)
        jlink.connect(jlink_name)
        jlink.set_little_endian()

        return jlink

    async def connect_jlink(self, jlink_serial, jlink_name):
        self._jlink = await self._loop.run_in_executor(
            self._connect_jlink_blocking, jlink_serial, jlink_name)

        return self._jlink

    async def close_jlink(self):
        if self._jlink is not None:
            await self._loop.run_in_executor(self._jlink.close)
            self._jlink = None

    async def start_polling(self, control_info, step_timeout=0.1):
        counter = self._maintenance_counter
        self._maintenance_counter += 1

        if counter == 0:
            self._maintenance_task = self._loop.add_task(
                self._maintenance_coroutine(control_info, step_timeout))

    async def stop_polling(self):
        self._maintenance_counter -= 1
        if self._maintenance_counter == 0:
            await self._maintenance_task

    async def register_read(self, pc_reg):
        return await self._loop.run_in_executor(self._jlink.register_read, pc_reg)

    async def reset(self, halt=False):
        await self._loop.run_in_executor(self._jlink.reset, halt=halt)

    def _write_memory_blocking(self, start_address, data, chunk_size=4, raw_data=False):
        if raw_data:
            write_fn = self._jlink.memory_write
        else:
            if chunk_size == 1:
                write_fn = self._jlink.memory_write8
            elif chunk_size == 2:
                write_fn = self._jlink.memory_write16
            elif chunk_size == 4:
                write_fn = self._jlink.memory_write32
            else:
                raise ArgumentError("_write_memory_blocking chunk_size {} is not valid".format(chunk_size))

        return write_fn(start_address, data)

    async def write_memory(self, start_address, data, chunk_size=4, raw_data=False):
        """ Preferable async version of jlink.memory_writeXX """
        return await self._loop.run_in_executor(self._write_memory_blocking,
            start_address, data, chunk_size, raw_data)

    def _read_memory_blocking(self, start_address, length, chunk_size=4, join=True):
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

    async def read_memory(self, start_address, length, chunk_size=4, join=True):
        """ Prefable async version for jlink.memory_readXX """
        return await self._loop.run_in_executor(self._read_memory_blocking,
            start_address, length, chunk_size, join)

    async def _poll_rpc_status(self, control_info):
        poll_address, poll_mask = control_info.poll_info()
        value, = await self.read_memory(poll_address, 1, chunk_size=1)

        if value & poll_mask:
            self.rpc_response_event.set()

    async def _maintenance_coroutine(self, control_info, step_timeout):
        while self._maintenance_counter > 0:
            if self._jlink_adapter.opened_interfaces["rpc"]:
                await self._poll_rpc_status(control_info)

            await asyncio.sleep(step_timeout)

    async def find_control_structure(self, start_address, search_length):
        """Find the control structure in RAM for this device.

        Returns:
            ControlStructure: The decoded contents of the shared memory control structure
                used for communication with this IOTile device.
        """

        words = await self.read_memory(start_address, search_length, chunk_size=4, join=False)
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

    async def verify_control_structure(self, device_info, control_info=None):
        """Verify that a control structure is still valid or find one.

        Returns:
            ControlStructure: The verified or discovered control structure.
        """

        if control_info is None:
            control_info = await self.find_control_structure(device_info.ram_start, device_info.ram_size)

        #FIXME: Actually reread the memory here to verify that the control structure is still valid
        return control_info
