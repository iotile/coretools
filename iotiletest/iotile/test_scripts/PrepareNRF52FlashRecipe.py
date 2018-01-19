import subprocess, time, os, sys, csv
from iotile.core.hw.hwmanager import HardwareManager
from PrepareFlashRecipe import PrepareFlashRecipe

class PrepareNRF52FlashRecipe(PrepareFlashRecipe):
    def __init__(self, chip_name, segger_id, executive_file, application_file, softdevice_file, uuid):
        super(PrepareNRF52FlashRecipe, self).__init__(chip_name, segger_id, executive_file, application_file)
        self._softdevice_file   = softdevice_file
        self._uuid              = uuid
        self._mac               = None
        
    def _flash_softdevice(self, path):
        print("--> Erasing chip and writing softdevice")
        output = subprocess.check_output(['nrfjprog.exe', '--program', path, '-f', 'nrf52', '--chiperase'])
        return output

    def _find_item(self, scan, mac, uuid):
        for item in scan:
            if item['connection_string'] == mac and item['uuid'] == uuid:
                print "--> SUCCESS!"
                return True
        print "--> **FAILURE**"
        return False

    def _get_macaddr(self):
        
        
        output = subprocess.check_output(['arm-none-eabi-gdb.exe', '-q',
            '-ex', 'target remote localhost:2331',
            '-ex', 'x (0x10000000UL + 0x0A4)',
            '-ex', 'x (0x10000000UL + 0x0A4 + 4)',
            '-ex' ,'set confirm off',
            '-ex', 'quit'])
        
        lines   = [x.rstrip() for x in output.split('\n')]

        import pdb
        pdb.set_trace()
        
        maclow  = lines[2]
        machigh = lines[3]

        lowaddr, lowval     = maclow.split('\t')
        highaddr, highval   = machigh.split('\t')

        lowval  = int(lowval, 0)
        highval = int(highval, 0)

        highval = (highval & 0xFFFF) | (0b11 << 14)

        macval  = (highval << 32) | lowval
        mac     = ":".join(reversed(["%0.2X" % (((macval & ((0xFF) << (8*i))) >> (8*i)),)[:2] for i in xrange(0, 6)]))
        print("--> MAC Address was: " + mac)
                    
        self._mac = mac

    def _set_uuid(self):
        print('--> Setting UUID to %x' % self._uuid)

        with HardwareManager(port='bled112:<auto>,%s' % self._mac) as hw:
            con = hw.controller()
            con.sensor_graph().set_uuid(self._uuid)

            print("--> Resetting device")
            con.reset()
            
            hw.disconnect()

            print("--> Scanning for new UUID")
            time.sleep(2)
            items = hw.scan()

            return self._find_item(items, self._mac, self._uuid)

    def load(self):
        if(self._open_gdb_server()):
            self._flash_softdevice(self._softdevice_file)
            self._load_exec_and_app()
            self._get_macaddr()           
            self._close_gdb_server()

            raw_input('--> Press return after rebooting')

            return self._set_uuid()
            
        else:
            return False



        