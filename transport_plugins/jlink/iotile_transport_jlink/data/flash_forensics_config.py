import os

ff_bin_filename   = "flash_forensics.bin"
ff_data_directory = "data"

ff_relative_bin_path = ff_data_directory + "\\"+ ff_bin_filename

ff_absolute_bin_path = os.path.dirname(os.path.realpath(__file__)) + "\\" + ff_bin_filename


# FF_CMD_INFO Byte Layout

# 0x2000FFE0: ff_cmd_info.command.id
# 0x2000FFE1: ff_cmd_info.command.reserved[0]
# 0x2000FFE2: ff_cmd_info.command.reserved[1]
# 0x2000FFE3: ff_cmd_info.command.reserved[2]
# 0x2000FFE4: ff_cmd_info.command.read_cmd.address
# 0x2000FFE8: ff_cmd_info.command.read_cmd.length
# 0x2000FFEA: ff_cmd_info.command.read_cmd.reserved[0]
# 0x2000FFEB: ff_cmd_info.command.read_cmd.reserved[1]
# 0x2000FFEC: ff_cmd_info.response.id
# 0x2000FFED: ff_cmd_info.response.error_code
# 0x2000FFED: ff_cmd_info.response.reserved[0]
# 0x2000FFEF: ff_cmd_info.response.reserved[1]
# 0x2000FFF0: ff_cmd_info.response.read_resp.buffer_addr
# 0x2000FFF4: ff_cmd_info.response.read_resp.offset
# 0x2000FFF6: ff_cmd_info.response.read_resp.reserved[0]
# 0x2000FFF7: ff_cmd_info.response.read_resp.reserved[1]
# 0x2000FFF8: ff_cmd_info.max_read_length
# 0x2000FFFA: ff_cmd_info.max_write_length
# 0x2000FFFC: ff_cmd_info.reserved[0]
# 0x2000FFFD: ff_cmd_info.reserved[1]
# 0x2000FFFE: ff_cmd_info.reserved[2]
# 0x2000FFFF: ff_cmd_info.reserved[3]

# FF_CMD_INFO Byte Layout
ff_addresses = {
    'blob_inject_start' : 0x20002128,
    'program_start' : 0x20002e78,
    'command_id' : 0x2000FFE0,
    'read_command_address' : 0x2000FFE4,
    'read_command_length' : 0x2000FFE8,
    'response_id' : 0x2000FFEC,
    'response_error_code' : 0x2000FFED,
    'read_response_buffer_address' : 0x2000FFF0,
    'read_response_offset' : 0x2000FFF4,
    'max_read_length' : 0x2000FFF8,
    'max_write_length' : 0x2000FFFA
}
