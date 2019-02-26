"""Information about known device types that we can control over jlink."""
from collections import namedtuple

RPCTriggerViaSWI = namedtuple('RPCTriggerViaSWI', ['register', 'bit'])

DeviceInfo = namedtuple('DeviceInfo', ['jlink_name', 'ram_start', 'ram_size', 'flash_start', 'flash_size', 'rpc_trigger'])

# NRF52 has RPCs triggered by sending SWI 0 which is IRQ bit 20 in the first NVIC control register
# See http://infocenter.arm.com/help/index.jsp?topic=/com.arm.doc.ddi0337e/Cihcbadd.html
NRF52 = DeviceInfo('nRF52832_xxAA', 0x20000000, 64*1024, 0, 512*1024, RPCTriggerViaSWI(0xE000E200, 20))
LPC824 = DeviceInfo('LPC824M201', 0x10000000, 8*1024, 0, 64*1024, None)

DEVICE_ALIASES = {
    'nrf52': 'nRF52832_xxAA',
    'lpc824': 'LPC824M201'
}

KNOWN_DEVICES = {
    'nRF52832_xxAA': NRF52,
    'LPC824M201': LPC824
}
