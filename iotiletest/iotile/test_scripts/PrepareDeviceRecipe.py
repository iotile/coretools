import os
import time
import tempfile
from iotile.core.exceptions import HardwareError, ArgumentError
from iotile.cloud.cloud import IOTileCloud

from iotile.sg.exceptions import SensorGraphSyntaxError, StreamEmptyError
from iotile.sg import DeviceModel
from iotile.sg.parser import SensorGraphFileParser
from iotile.sg.output_formats import known_formats
import iotile.sg.parser.language as language

class PrepareDeviceRecipe(object):
    def __init__(self, hw, args,
                desired_con_version, desired_con_path,
                desired_tile_versions, desired_tile_paths,
                desired_tile_names, desired_tile_addresses,
                desired_cloud_sg, desired_sgf_path,
                app_name, app_version, os_version, 
                unclaim = True, appended_test_fun = None):

        
        self._hw                        = hw
        self._con                       = self._hw.controller()
        self._rb                        = self._con.remote_bridge()

        self._desired_con_version       = desired_con_version
        self._desired_con_path          = desired_con_path
        self._desired_tile_versions     = desired_tile_versions
        self._desired_tile_paths        = desired_tile_paths
        self._desired_tile_names        = desired_tile_names
        self._desired_tile_addresses    = desired_tile_addresses
        self._desired_cloud_sg          = desired_cloud_sg
        self._desired_sgf_path          = desired_sgf_path
        self._app_name                  = app_name
        self._app_version               = app_version
        self._os_version                = os_version
        self._unclaim                   = unclaim
        self._appended_test_fun         = appended_test_fun
    
    def test_device(self):
        info = self._con.test_interface().get_info()
        print("--> Checking app version: expected=%d, actual=%d" % (app_version, info['app_version']))
        print("--> Checking os version:  expected=%d, actual=%d" % (os_version, info['os_version']))

        self._hw.enable_streaming()
        
        print("--> Testing realtime data (takes 2 seconds)")
        time.sleep(2.0)

        accel = self._hw.get(12)
        env = self._hw.get(13)

        print("--> Accel: %d Shocks" % accel.count_shocks())
        print("--> Env: Temperature= %s Pressure=%s Relative Humidity= %s" % \
            (env.sample_temperature(), env.sample_pressure(), env.sample_humidity()))

        reports = [x for x in hw.iter_reports()]
        if not len(reports) >= 4:
            print("-->Realtime data is not coming from device")
            raise HardwareError("Failure reading data from device")

    def check_cloud_setup(self, args):
        """Make sure the device is properly configured in the cloud
        """
        hw_info = self._hw.controller().test_interface().get_info()
        device_id = hw_info['device_id']


        cloud = IOTileCloud()
        info = cloud.device_info(device_id)
        
        
        if info['sg'] != self._desired_cloud_sg:
            print("--> Updating cloud sensorgraph from %s to %s" % (info['sg'], self._desired_cloud_sg))
            cloud.set_sensorgraph(device_id, self._desired_cloud_sg)

        if self._unclaim:
            print("--> Unclaiming device")
            cloud.unclaim(device_id)

    def load_sg(self):
        """Get the SGF file and load the sensorgraph and config variables into the unit
        """
        print("--> Loading sensorgraph")

        parser = SensorGraphFileParser()
        parser.parse_file(os.path.join(os.path.dirname(__file__),  desired_sgf_filename))
        model = DeviceModel()
        parser.compile(model=model)
        parsed_sg = parser.sensor_graph

        sg = self._con.sensor_graph()
        conf = self._con.config_database()

        #Writing nodes in sgf file into unit's sensor graph
        sg.disable()
        sg.reset()
        sg_ascii_filename       = os.path.join(os.path.dirname(__file__), 'ascii_sg')
        config_ascii_filename   = os.path.join(os.path.dirname(__file__), 'ascii_conf')

        with open(sg_ascii_filename,'wb') as sg_ascii_file:
            sg_ascii_file.write(known_formats['ascii'](parsed_sg))
        
        sg.load_from_file(sg_ascii_filename)
        os.remove(sg_ascii_filename)

        sg.persist()
        sg.clear()
        sg.enable()

        #Writing config variables in sgf file into unit's config database
        conf.clear_variables()
        with open(config_ascii_filename,'wb') as config_ascii_file:
            config_ascii_file.write(known_formats['config'](parsed_sg))    
        
        conf.load_from_file(config_ascii_filename)
        os.remove(config_ascii_filename)

        self._con.reset()

    def check_and_upgrade_tile_fw(self):
        #Verifying Tiles
        for i in range(len(self._desired_tile_addresses)):
            address             = self._desired_tile_addresses[i]
            desired_tile_name   = self._desired_tile_names[i]
            fw_name             = self._desired_tile_fw_paths[i]
            desired_version     = self._desired_tile_fw_versions[i]

            try:
                tile         = hw.get(address)
                tile_name    = tile.tile_name()
                tile_version = ".".join([str(x) for x in tile.tile_version()])
            except HardwareError:
                raise HardwareError("No tile exists on address %d" % (address))

            if tile_name != desired_tile_name:
                raise HardwareError("Wrong/No tile exists on address %d, should be tile %s" % (address, desired_tile_name))

            if tile_version != desired_version:
                print("--> %s Tile firmware out of date, updating firmware" % tile_name)
                rb.reflash_tile("slot %d" % (address-10), os.path.join(os.path.dirname(__file__), '..', fw_name))


    def check_and_upgrade_nrf52_fw(self):
        con_version = ".".join([str(x) for x in self._con.tile_version()])
        #Make sure we have a modern firmware that exposes enough info for us to work
        try:
            info = self._con.test_interface().get_info()
        except HardwareError:
            raise HardwareError("The firmware on your controller is too old to use this script, please update it manually.", version=con_version)

        uuid = info['device_id']
        update_con = False
        print("--> Controller firmware version: %s" % con_version)
        if con_version != self._desired_con_version:
            print("--> Controller firmware out of date, updating firmware")
            update_con = True

        hw_version = self._con.hardware_version()

        if hw_version == 'btc1_v2':
            con_firmware = os.path.join(os.path.dirname(__file__), '..', 'connrf52832_nrf52832_v2.elf')
            print("--> Hardware Type: ES1")
        elif hw_version == 'btc1_v3':
            con_firmware = os.path.join(os.path.dirname(__file__), '..', 'connrf52832_nrf52832_v3.elf')
            print("--> Hardware Type: Production")
        else:
            raise HardwareError("Unknown hardware type", found=hw_version, expected="btc1_v2 or btc1_v3")

        rb = self._con.remote_bridge()
        rb.create_script()

        if update_con:
            rb.add_reflash_controller_action(con_firmware)
            rb.add_setuuid_action(uuid)

        rb.add_setversion_action('app', app_version)
        rb.add_setversion_action('os', os_version) 
        print("--> Sending script to device.")
        rb.send_script()

        if update_con:
            print("--> Waiting 10 seconds for controller to reflash itself.")
            rb.trigger_script()
            time.sleep(10)

            #FIXME: This will not be necessary once remotebridge supports reconnecting after controller reflash
            if not self._hw.stream.connection_interrupted:
                raise HardwareError("Did not detect a controller reflash, FAILING.")

            self._hw.stream.connected = False
            self._hw.stream._connect_direct(hw.stream.connection_string)
            self._hw.stream.connection_interrupted = False
            self._hw.stream.connected = True

            #Reenable streaming interface if that was open before as well
            if self._hw.stream._reports is not None:
                res = self._hw.stream.adapter.open_interface_sync(0, 'streaming')
                if not res['success']:
                    raise HardwareError("Could not open streaming interface to device", reason=res['failure_reason'])
        else:
            rb.wait_script()


    def prepare(self):
        print("--> Configuring device as a {}".format(self._app_name))

        self.check_and_upgrade_nrf52_fw()
        self.check_and_upgrade_tile_fw()
        self.load_sg()
        self.test_device()
        self.check_cloud_setup(args)

