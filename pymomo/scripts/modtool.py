#!/usr/bin/env python

import sys
import os.path
import os
import intelhex
from time import sleep
import datetime

from pymomo.commander.meta import *
from pymomo.commander.exceptions import *
from pymomo.hex16.convert import *
import cmdln
from colorama import Fore, Style
import pytest
from tempfile import NamedTemporaryFile

import struct

class ModTool(cmdln.Cmdln):
	name = 'modtool'

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_list(self, subcmd, opts):
		"""${cmd_name}: List all attached MIB modules on the bus
		
		${cmd_usage}
		${cmd_option_list}
		"""

		con = self._get_controller(opts)
		try:
			mods = con.enumerate_modules()
		except RPCException as e:
			print e.type
			print e.data

		print "Listing attached modules"
		for i, mod in enumerate(mods):
			print "%d: %s at address %d" % (i, mod.name, mod.address)

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-v', '--voltage', action='store_true', help='Display the MoMo battery voltage')
	def do_status(self, subcmd, opts):
		"""${cmd_name}: Report the attached momo device's status

		${cmd_usage}
		${cmd_option_list}
		"""

		con = self._get_controller(opts)

		if opts.voltage:
			print "Battery Voltage: %.2fV" % con.battery_status()

	def do_test(self, subcmd, opts, *tests):
		"""${cmd_name}: Run hardware tests on attached MoMo device

		Call with list as the only argument to see all of the different
		tests that are available.  Call with no arguments to run all tests.
		Call with test class names to run only those tests.

		${cmd_usage}
		${cmd_option_list}
		"""

		if len(tests) == 1 and tests[0] == 'list':
			test_string = '--collect-only'
		else:
			test_string = " ".join(map(lambda x: "-k " + x, tests))

		pytest.main('--pyargs pymomo %s' % test_string)

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_reset(self, subcmd, opts):
		con = self._get_controller(opts)
		con.reset()

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_factory_reset(self, subcmd, opts):
		really = raw_input("Are you sure you want to reset the device to factory defaults?  Data will be lost.  [y/N]: ")
		if ( really == "y" or really == "Y" or really == "yes" or really == "Yes" ):
			con = self._get_controller(opts)
			con.factory_reset()
		else:
			print "Cancelled!"

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_recover(self, subcmd, opts):
		con = self._get_controller(opts)

		print 'Attempting Recovery...'
		con.set_alarm(True)

		if not con.alarm_asserted():
			print "Could not set ALARM pin, bailing..."
			return 1

		raw_input("Please cycle power on the attached MoMo...(press return when done)")
		sleep(0.5)
		con.set_alarm(False)


		if not con.alarm_asserted():
			print "DID NOT DETECT REFLASH IN PROGRESS, AN ERROR PROBABLY OCCURRED..."
			return 1
		else:
			print 'Waiting for reflash to complete'

		while con.alarm_asserted():
			sys.stdout.write('.')
			sys.stdout.flush()
			sleep(0.1)

		print '\nReflash complete'

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_fsu(self, subcmd, opts, command):
		"""${cmd_name}: Directly control the FSU that is connected to the MoMo unit.  

		Possible subcommands are heartbeat, reset and attached.  
		- heartbeat checks if the FSU is still there.
		- reset resets the FSU.
		- attached determines if a MoMo unit is plugged in to the FSU.

		${cmd_usage}
		${cmd_option_list}
		"""

		commands = set(["reset", "heartbeat", "attached"])

		con = self._get_controller(opts)

		if command not in commands:
			print "Usage: modtool fsu [reset|heartbeat|attached]"
			return 1

		if command == "heartbeat":
			if con.stream.heartbeat() is False:
				print "FSU Heartbeat NOT DETECTED, try resetting it with modtool reset -f"
				return 1
			else:
				print "FSU Heartbeat detected"
		elif command == "reset":
			status = con.stream.reset()
			if status is False:
				print "FSU reset NOT SUCCESSFUL, try unplugging and replugging it from both the MoMo and computer at the same time."
				return 1
			else:
				print "FSU reset successful"
		elif command == "attached":
			if con.momo_attached():
				print "MoMo unit: Attached"
			else:
				print "NO MOMO UNIT ATTACHED"

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_alarm(self, subcmd, opts, *asserted):
		con = self._get_controller(opts)


		if len(asserted) == 0:
			status = con.alarm_asserted()

			if status:
				message = "Asserted"
			else:
				message = "Idle"
			print "Alarm status: %s" % message
		elif len(asserted) == 1:
			cmd = asserted[0]
			if cmd == "assert":
				con.set_alarm(True)
			elif cmd == "clear":
				con.set_alarm(False)
			else:
				print "Unknown command passed to modtool alarm: %s" % cmd

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-t', '--type', choices=['module', 'controller', 'backup'], default='module', help='What type of firmware module (module, controller, backup)')
	@cmdln.option('-c', '--clear', action='store_true', default=False, help='Clear the firmware cache before pushing')
	def do_push(self, subcmd, opts, hexfile):
		"""${cmd_name}: Push a firmware file to the attached momo unit.  

		You can either push the firmware into the 4 module firmware bins,
		the main controller firmware bin or the backup controller firmware
		bin.  Use -c to clear the controller's firmware cache before pushing.

		${cmd_usage}
		${cmd_option_list}
		"""

		con = self._get_controller(opts)

		if opts.clear:
			con.clear_firmware_cache()

		processed = hexfile

		if opts.type == "module":
			type = 0
			print "Pushing module firmware"
		elif opts.type == "controller":
			type = 5
			processed = self._convert_hex24(hexfile)
			print "Pushing (processed) main controller firmware"
		elif opts.type == "backup":
			type = 6
			processed = self._convert_hex24(hexfile)
			print "Pushing (processed) backup controller firmware"

		con.push_firmware(processed, type, verbose=True)

		#If we created a new processed file, remove it
		if processed != hexfile:
			os.remove(processed)

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-b', '--bucket', type=int, help='Firmware bucket to pull from (0-5)')
	def do_pull(self, subcmd, opts, hexfile):
		"""${cmd_name}: Pull a firmware file from the attached momo unit.  

		The firmware from the given bucket is pulled and saved to a file. 
		If the bucket is 4 or 5, the firmware is padded out to 4-byte words
		from 24 bit words since those two buckets are pic24 firmwares.  Otherwise
		the firmware is saved as is.

		${cmd_usage}
		${cmd_option_list}
		"""

		if opts.bucket >= 6:
			print "Invalid bucket %d: must be in [0, 5]" % opts.bucket

		if opts.bucket >= 4:
			pic12 = False
		else:
			pic12 = True

		con = self._get_controller(opts)
		hexobj = con.pull_firmware(opts.bucket, pic12=pic12, verbose=True)

		if not pic12:
			hexobj = pad_pic24_hex(hexobj)

		hexobj.write_hex_file(hexfile)


	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-l', '--length', choices=['8', '16', '24', '32'], default=16)
	def do_read(self, subcmd, opts, address):
		"""${cmd_name}: Read firmware directly from flash.

		${cmd_usage}
		${cmd_option_list}
		"""

		con = self._get_controller(opts)

		ltable = {'8': 1, '16': 2, '24': 3, '32': 4}

		addr = int(address, 0)
		res = con.read_flash(addr, ltable[opts.length], verbose=False)

		if opts.length == '8':
			num = res[0]
		elif opts.length == '16':
			num = res[0] | (res[1] << 8)
		elif opts.length == '24':
			num = res[0] | (res[1] << 8) | (res[2] << 16)
		elif opts.length == '32':
			num = res[0] | (res[1] << 8) | (res[2] << 16) | (res[3] << 24)

		print '0x%X' % num
		
	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_info(self, subcmd, opts, index):
		"""${cmd_name}: Describe the mib module given its index

		Index is returned by mobtool list
		${cmd_usage}
		${cmd_option_list}
		"""
		
		con = self._get_controller(opts)
		mod = con.describe_module(int(index))

		print "Module at index %d" % int(index)
		print "Name: %s" % mod.name
		print "Type: %d" % mod.type
		print "Flags: %d" % mod.flags
		print "Address: %d" % mod.address
		print "Features: %d" % mod.num_features

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-a', '--address', default=None, help='Select device by address')
	@cmdln.option('-n', '--name', default=None, help='Select device by name')
	@cmdln.option('-c', '--controller', action='store_true', default=False, help='Reflash the controller')
	@cmdln.option('--noreset', action='store_true', default=False, help='Do not reset the bus after the reflash')
	def do_reflash(self, subcmd, opts, hexfile):
		"""${cmd_name}: Reflash the mib12 module given either its name or address 

		If name is passed, the first mib module with that name is reflashed.  If
		address is passed, the address must match a currently attached module and
		that module will be reflashed.  You must pass either an address or a name,
		but not both.

		HEXFILE should be a valid mib12 application module.  The controller firmware
		cache will be cleared during the reflashing process and the module in question
		will be reset. 
		
		${cmd_usage}
		${cmd_option_list}
		"""

		con = self._get_controller(opts)

		if opts.controller:
			reflash_controller(con, hexfile)
		else:
			reflash_module(con, hexfile, name=opts.name, address=int(opts.address), noreset=opts.noreset)

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_time(self, subcmd, opts):
		"""${cmd_name}: Get the current RTCC time according to the controller module.

		${cmd_usage}
		${cmd_option_list}
		"""

		con = self._get_controller(opts)

		print con.current_time()

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_battery(self, subcmd, opts):
		"""${cmd_name}: Get the current battery voltage

		${cmd_usage}
		${cmd_option_list}
		"""

		con = self._get_controller(opts)

		print con.battery_status()

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_scheduler(self, subcmd, opts, command, index = None):
		"""${cmd_name}: Manage scheduled callbacks

		Possible subcommands are heartbeat, reset and attached.  
		- new creates a new dummy scheduled task (address 43, feature 20, command 8, frequency 1s)
		- remove removes the dummy scheduled task
		- map returns the map of task buckets
		- describe <index> describes the callback at index <index>

		${cmd_usage}
		${cmd_option_list}
		"""

		con = self._get_controller(opts)
		if command == "map":
			print bin( con.scheduler_map() )
		elif command == "new":
			con.scheduler_new(43, 20, 8, 1)
		elif command == "remove":
			con.scheduler_remove(43, 20, 8, 1)
		elif command == "describe":
			if index == None:
				print "You must specify a scheduler index to describe."
				exit(1)
			callback = con.scheduler_describe(index)
			if callback == None:
				print "No scheduled callback found at index %d" % int(index)
				exit(1)
			print "Address: %d" % int(callback[0])
			print "Feature: %d" % int(callback[1])
			print "Command: %d" % int(callback[2])
			if callback[3] == 0:
				frequency = "Every half second"
			elif callback[3] == 1:
				frequency = "Every second"
			elif callback[3] == 2:
				frequency = "Every 10 seconds"
			elif callback[3] == 3:
				frequency = "Every minute"
			elif callback[3] == 4:
				frequency = "Every 10 minutes"
			elif callback[3] == 5:
				frequency = "Every hour"
			elif callback[3] == 6:
				frequency = "Every day"
			else:
				frequency = "<unknown>"

			print "Frequency: %s" % frequency

		else:
			print "Invalid subcommand specified for command 'scheduler'."
			exit(1)

	def _get_controller(self, opts):
		try:
			c = get_controller(opts.port)
		except NoSerialConnectionException as e:
			print "Available serial ports:"
			if not e.available_ports():
				print "<none>"
			else:
				for port, desc, hwid in e.available_ports():
					print "\t%s (%s, %s)" % ( port, desc, hwid )
			self.error(str(e))
		except ValueError as e:
			self.error(str(e))

		return c

	def _convert_hex24(self, hexfile):
		tmpf = NamedTemporaryFile(delete=False)
		tmpf.close()

		tmp = tmpf.name

		out = unpad_pic24_hex(hexfile)
		out.write_hex_file(tmp)
		return tmp

	def error(self, text):
		print Fore.RED + "Error Occurred: " + Style.RESET_ALL + text
		sys.exit(1)

def main():
	modtool = ModTool()
	return modtool.main()