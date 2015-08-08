from pymomo.commander.proxy import proxy
from pymomo.commander.proxy import proxy12
import pymomo.commander.proxy
from pymomo.commander.exceptions import *
from pymomo.commander.types import *
from pymomo.utilities.console import ProgressBar
import struct
from pymomo.utilities.intelhex import IntelHex
from time import sleep
from datetime import datetime
from pymomo.syslog import RawLogEntry, SystemLog
from pymomo.utilities.typedargs.annotate import annotated,param,returns, context, return_type
from pymomo.utilities import typedargs
from pymomo.utilities.typedargs import type_system, iprint
from pymomo.exceptions import *
from tempfile import NamedTemporaryFile
from pymomo.hex16.convert import *
import pymomo.hex
import itertools
import base64
import uuid
import os
import sys

#Formatters for the return types used in this class
def print_module_list(mods):
	print "Listing attached modules"
	for i, mod in enumerate(mods):
		print "%d: %s at address %d" % (i, mod.name, mod.address)

def _print(x):
	print x

@context("MIBController")
class MIBController (proxy.MIBProxyObject):
	"""
	A python proxy object for interacting with the MoMo controller board.
	"""

	MaxModuleFirmwares = 4

	@annotated
	def __init__(self, stream, address=8):
		super(MIBController, self).__init__(stream, address)
		self.name = 'Controller'

	@returns(desc='number of attached module', data=True)
	def count_modules(self):
		"""
		Count the number of attached devices to this controller
		"""

		res = self.rpc(42, 1, result_type=(1, False))
		return res['ints'][0]

	def _reflash(self):
		try:
			self.rpc(42, 0xA)
		except ModuleNotFoundError:
			pass

	def describe_module(self, index):
		"""
		Describe the module given its module index
		"""
		res = self.rpc(42, 2, index, result_type=(0,True))

		return ModuleDescriptor(res['buffer'], 11+index)

	@annotated
	def clear_log(self):
		"""
		Clear the MoMo system log.
		"""

		self.rpc(42,0x23)

	@annotated
	def read_log(self):
		"""
		Read the MoMo system log
		"""
		count = self.rpc(42, 0x21, result_type=(1,False))['ints'][0]

		log = []

		pb = ProgressBar("Downloading %d log entries" % count, count)

		pb.start()
		for i in xrange(0, count):
			res = self.rpc(42, 0x22, i, 0, result_type=(0, True))
			try:
				log.append(RawLogEntry(res['buffer']))
			except ValidationError as e:
				iprint("FAILED TO PARSE A LOG ENTRY, %d entries discarded" % (count - i))
				break

			pb.progress(i)

		pb.end()

		return SystemLog(log)

	def _convert_hex24(self, hexfile):
		"""
		Convert a hex file for the pic24 from 4 bytes per 2 words to 3 bytes per two words

		This is how the file is stored on the MoMo Controller to save space.
		"""

		tmpf = NamedTemporaryFile(delete=False)
		tmpf.close()

		tmp = tmpf.name

		out = unpad_pic24_hex(hexfile)
		out.write_hex_file(tmp)
		return tmp

	@param("hexfile", "path", "readable", desc="Hex file containing firmware to flash")
	@param("name", "string", desc="Name of module to reflash")
	@param("noreset", "bool", desc="Do not reset the bus after reflash is complete")
	def reflash_module(self, hexfile, name, noreset=False):
		"""
		Reflash a mib module given its name.
		"""

		#Enter safe mode and wait for the modules to all reregister
		#self.enter_safe_mode()
		#sleep(2)

		#Make sure the module exists before pushing the firmware
		mod = self.get_module(name=name, force=False)

		self.clear_firmware_cache()
		bucket = self.push_firmware(hexfile, 0)

		mod.rpc(0, 5, 8, bucket)
		mod.reset()

		try:
			sleep(1.5)
			if not self.alarm_asserted():
				iprint("Module reflash NOT DETECTED.  Verify the module checksum to ensure it is programmed correctly.")
				raise HardwareError("Could not reflash module, reflash not detected using alarm pin.")

			iprint("Reflash in progress")

			while self.alarm_asserted():
				if type_system.interactive:
					sys.stdout.write('.')
					sys.stdout.flush()
				sleep(0.1)
		except StreamOperationNotSupportedError:
			iprint("Waiting 12 seconds for module to reflash itself.")
			sleep(12.)

		iprint("\nReflash complete.")

		sleep(0.5)

		if not noreset: 
			iprint("Resetting the bus...")

		self.reset(sync=True)

	@param("hexfile", "path", "readable", desc="new controller hex file")
	def reflash(self, hexfile):
		"""
		Reflash the controller with a new application image.

		Given a path to a hexfile, push it onto the controller and then
		tell the controller to reflash itself.  This is a synchronous command
		that will return once the reflash operation is complete and the new code
		is running on the controller.  Any errors in the process will be raised.
		"""

		processed = self._convert_hex24(hexfile)
		self.push_firmware(processed, 5)
		os.remove(processed)
		self._reflash()

		try:
			sleep(0.5)
			if not self.alarm_asserted():
				raise HardwareError("Could not reflash controller", reason="Controller reflash NOT DETECTED.  You may need to try the recovery procedure.")

			iprint("Reflash in progress")

			while self.alarm_asserted():
				if type_system.interactive:
					sys.stdout.write('.')
					sys.stdout.flush()

				sleep(0.1)
		except StreamOperationNotSupportedError:
			iprint("Waiting 7 seconds for module to reflash itself.")
			sleep(7.0)

		iprint("\nReflash complete.")

	@param("name", "string", desc="module name")
	@param("address", "integer", ("range", 11, 127), desc="modules address")
	@param("type", "string", desc="type of proxy object to return")
	def get_module(self, name=None, address=None, force=False, type=None):
		"""
		Given a module name or a fixed address, return a proxy object
		for that module if it is connected to the bus.  If force is True
		this call will construct an proxy object for the given address even
		if the module is not found in the controller's database of connected
		modules.
		"""

		if address is not None and force:
			obj = proxy12.MIB12ProxyObject(self.stream, address)
			obj.name = 'Unknown'
			return obj

		mods = self.list_modules()
		if name is not None and len(name) < 6:
			name += (' '*(6 - len(name)))

		for mod in mods:
			if name == mod.name or address == mod.address:
				typeobj = proxy12.MIB12ProxyObject
				if type is not None:
					return self.hwmanager._create_proxy(type, mod.address)

				if typeobj is None:
					raise ArgumentError("Could not find proxy module for specified type", type=type, known_types=self.hwmanager.name_map.keys())

				obj = typeobj(self.stream, mod.address)
				obj.name = mod.name
				return obj

		raise ArgumentError("Could not find module by name or address", name=name, address=address, attached_modules=[mod.name for mod in mods])

	@returns(desc='list of attached modules', printer=print_module_list, data=True)
	def list_modules(self):
		"""
		Get list of all attached modules and describe them all
		"""

		num = self.count_modules()

		mods = []

		for i in xrange(0, num):
			mods.append(self.describe_module(i))

		return mods

	def get_debug_value(self):
		"""
		Return the current value of the debug flag in the controller.
		This is an unsigned integer that can be used to signal that 
		processes are ocurring or not occuring as they should.
		"""

		res = self.rpc(42, 0x0D, result_type=(1, False))
		flag = res['ints'][0]
		return flag

	def set_sleep(self, val):
		"""
		Enable or disable sleeping on the controller when there are no tasks 
		to perform.  val should be True to enable sleeping, False to disable 
		it. 
		"""
		res = self.rpc(42, 0x0E, int(bool(val)))

	@return_type("float")
	def battery_level(self):
		res = self.rpc(42, 0x0B, result_type=(1, False))
		volt_raw = res['ints'][0]

		volt = volt_raw/1024. * 2.78 * 2.0 	#ADC is on a divide by 2 resistor network with a VCC reference
		return volt

	def _encode_firmware_line(self, line):
		if line[0] != ':':
			raise ValueError("Invalid hex line, did not start with a ':': %s" % line)

		line = line[1:]

		cnt = int(line[0:2], 16)
		addr = int(line[2:6], 16)
		rec = int(line[6:8], 16)

		if cnt > 16:
			raise ValueError("Cannot use hex file with more than 16 bytes per line. Line size was %d." % cnt)

		datahex = line[8:8+2*cnt]
		chk = int(line[8+2*cnt:8+2*cnt+2], 16)

		data = bytearray(cnt)
		for i in xrange(0, cnt):
			data[i] = int(datahex[2*i:2*i+2], 16)

		packed = struct.pack('HB%dB' % cnt, addr, rec, *data)
		return bytearray(packed)

	@param("hexfile", "path", "readable", desc="path of backup firmware image to load")
	def push_backup(self, hexfile):
		"""
		Push a recovery firmware image to the controller
		"""

		processed = self._convert_hex24(hexfile)
		iprint("Pushing (processed) backup controller firmware")
		self.push_firmware(processed, 6, verbose=True)
		os.remove(processed)

	def push_firmware(self, firmware, module_type, verbose=True):
		"""
		Given either a path to a hex file or an open file-like object,
		push the firmware described by the object to the controller.

		returns an integer, which is the firmware bucket that this
		firmware was pushed to.
		"""

		lines = []

		if hasattr(firmware, "readlines"):
			lines = firmware.readlines()
		elif isinstance(firmware, basestring):
			with open(firmware, "r") as f:
				lines = f.readlines()

		if len(lines) == 0:
			raise ValueError("Could not understand firmware object type.  Should be a path or a file object")


		if verbose:
			print "Sending Firmware"
			prog = ProgressBar("Transmission Progress", len(lines))
			prog.start()

		res = self.rpc(7, 0, module_type, result_type=(1, False))
		bucket = res['ints'][0]

		for i in xrange(0, len(lines)):
			buf = self._encode_firmware_line(lines[i])
			res = self.rpc(7, 1, buf)

			if verbose:
				prog.progress(i+1)

		if verbose:
			prog.end()
			print "Firmware stored in bucket %d" % bucket

		return bucket

	@param("bucket", "integer", ("range", 0, 5), desc="Firmware bucket to pull from [0-5]")
	@param("save", "path", desc="Output file to save")
	@param("raw", "bool", desc='Do not process the result in any way')
	def pull_firmware(self, bucket, save=None, raw=False):
		res, reason = self._firmware_bucket_loaded(bucket)

		if res == False:
			raise ValueError(reason)

		if bucket < 4:
			pic12 = True
		else:
			pic12 = False

		info = self.get_firmware_info(bucket)
		length = info['length']

		out = IntelHex()

		iprint("Getting Firmware, size=0x%X" % length)
		prog = ProgressBar("Transmission Progress", length // 20)
		prog.start()

		for i in xrange(0, length, 20):
			res = self.rpc(7, 4, bucket, i, result_type=(0, True))

			for j in range(0, len(res['buffer'])):
				out[i+j] = ord(res['buffer'][j])
				if pic12 and (j%2 != 0):
					out[i+j] &= 0x3F

			prog.progress(i//20)

		prog.end()

		if not pic12 and not raw:
			out = pad_pic24_hex(out)
		
		if save is not None:
			out.write_hex_file(save)
			return 
		
		tmpf = NamedTemporaryFile(delete=False)
		tmpf.close()
		tmp = tmpf.name
		out.write_hex_file(tmp)

		if pic12:
			outhex = pymomo.hex.HexFile(tmp, 14, 2, 1)
		else:	
			outhex = pymomo.hex.HexFile(tmp, 24, 4, 2)

		os.remove(tmp)
		return outhex


	def _firmware_bucket_loaded(self, index):
		res = self.get_firmware_count()
		mods = res['module_buckets']

		if index < 4 and index >= mods:
			return False, "Invalid firmware bucket specified, only %d buckets are filled" % mods

		if index == 4 and not res['controller_firmware']:
			return False, "Controller firmware requested and none is loaded"

		if index == 5 and not res['backup_firmware']:
			return False, "Backup firmware requested and none is loaded"

		if index > 5:
			return False, "Invalid bucket index, there are only 6 firmware buckets (0-5)."

		return True, "" 

	def get_firmware_count(self):
		"""
		Return a dictionary containing:
		- the number of module firmwares loaded
		- if there is a controller firmware loaded
		- if there is a backup controller firmware loaded
		"""

		res = self.rpc(7, 5, result_type=(2, False))
		con = res['ints'][1]

		dic = {}
		dic['module_buckets'] = res['ints'][0]
		dic['controller_firmware'] = (con&0b1 == 1)
		dic['backup_firmware'] = ((con >> 1) == 1)

		return dic

	def clear_firmware_cache(self):
		self.rpc(7, 0x0A)

	def get_firmware_info(self, bucket):
		"""
		Get the firmware size and module type stored in the indicated bucket
		"""

		res = self.rpc(7, 3, bucket, result_type=(7, False))

		length = res['ints'][1] << 16 | res['ints'][2]
		base = res['ints'][3] << 16 | res['ints'][4]
		sub_start = res['ints'][5]
		subs = res['ints'][6]

		return {'module_type': res['ints'][0], 'length': length, 'base_address': base, 'bucket_start': sub_start, 'bucket_size': subs}

	def read_flash(self, baseaddr, count, verbose=True):
		"""
		Read count bytes of the controller's external flash starting at addr.
		The flash is read 20 bytes at a time since this is the maximum mib 
		frame size.
		"""

		if baseaddr >= 1024*1024:
			raise ValueError("Address too large, flash is only 1MB in size")

		buffer = bytearray()

		if verbose:
			prog = ProgressBar("Reading Flash", count)
			prog.start()

		for i in xrange(0, count, 20):
			if verbose:
				prog.progress(i)

			addr = baseaddr + i
			addr_low = addr & 0xFFFF
			addr_high = addr >> 16

			length = min(20, count-i)

			res = self.rpc(42, 3, addr_low, addr_high, result_type=(0, True))
			buffer.extend(res['buffer'][0:length])

		if len(buffer) != count:
			raise RuntimeError("Unknown error in read_flash, tried to read %d bytes, only read %d" % (count, len(buffer)))

		if verbose:
			prog.end()

		return buffer

	def write_flash(self, baseaddr, buffer, verbose=True):
		"""
		Write all of the bytes in buffer to the controller's external flash starting at baseaddr
		"""

		count = len(buffer)

		if baseaddr >= 1024*1024:
			raise ValueError("Address too large, flash is only 1MB in size")

		if verbose:
			prog = ProgressBar("Writing Flash", count)
			prog.start()

		i = 0
		while i < count:
			if verbose:
				prog.progress(i)

			addr = baseaddr + i
			addr_low = addr & 0xFFFF
			addr_high = addr >> 16

			length = min(14, count-i)		
			res = self.rpc(42, 4, addr_low, addr_high, buffer[i:i+length], result_type=(2, False))

			written_addr = res['ints'][0] | (res['ints'][1] << 16)

			if written_addr != addr:
				raise RuntimeError("Tried to write to address 0x%X but wrote to address 0x%X instead" % (addr, written_addr))

			i += length

		if verbose:
			prog.end()

	def erase_flash(self, addr):
		if addr >= 1024*1024:
			raise ValueError("Address too large, flash is only 1MB in size")

		addr_low = addr & 0xFFFF
		addr_high = addr >> 16

		res = self.rpc(42, 6, addr_low, addr_high)

	def bootloader_status(self):
		"""
		Check to see if the alarm pin is blinking at a fixed rate.  This is the
		bootloader's way of communicating with us, so figure out the pulse freq
		and match it to the bootloader's error code.
		"""

		alarm_codes = {
			100: "Invalid firmware magic number",
			150: "Invalid firmware checksum",
			200: "Invalid metadata checksum",
			250: "Hardware compatibility version does not match",
			300: "Address error (internal bootloader error)",
			350: "No firmware image loaded",
			400: "Wrong firmware length"
		}

		probe = []

		val = False
		for i in xrange(0, 400):
			down = self.alarm_asserted()
			if down != val:
				t = datetime.now()
				val = down
				probe.append(t)

			sleep(0.01)

		trans_pairs = itertools.izip(probe[2:], probe[1:-1])
		widths = map(lambda x: (x[0] - x[1]).total_seconds()*1000.0, trans_pairs)
		
		if len(widths) == 0:
			return "No Bootloader Error Detected"

		avg_width = sum(widths)/len(widths)

		code = min(alarm_codes.keys(), key=lambda x:abs(x-avg_width))

		return "Bootloader Error Detected: %s" % alarm_codes[code]


	def alarm_asserted(self):
		"""
		Query the field service unit if the alarm pin on the bus is asserted.  Returns True if 
		the alarm is asserted (low value since it's active low).  Returns False otherwise
		"""

		return self.hwmanager.check_alarm()

	def set_alarm(self, asserted):
		"""
		Instruct the field service unit to assert or deassert the alarm line on the MoMo bus.
		"""

		self.hwmanager.set_alarm(asserted)

	@param("value", "string", desc='Data to echo')
	@return_type("string")
	def echo(self, value):
		res = self.rpc(42, 0x28, value, result_type=(0,True))

		print len(value)
		print len(res['buffer'])
		print value
		print res['buffer']

	@return_type("map(string, string)")
	def bt_debug_log(self):
		"""
		Return the first 20 bytes of BTLE communication receive buffer.
		This contains the response to the last command sent to the unit.
		"""

		out = ""
		for i in xrange(0, 648, 20):
			res = self.rpc(42, 0x27, i, result_type=(0,True))
			out += res['buffer']

		fmt = "<H"

		flags, = struct.unpack_from(fmt, out)
		i = 2
		send = out[i:i+100]
		i += 100

		receive = out[i:i+256]
		i += 256

		cmd = out[i:i+26]
		i += 26

		transmitted_cursor, = struct.unpack_from(fmt, out[i:i+2])
		i+=2

		send_cursor, = struct.unpack_from(fmt, out[i:i+2])
		i+=2

		receive_cursor, = struct.unpack_from(fmt, out[i:i+2])
		i+=2

		checksum_errors, = struct.unpack_from(fmt, out[i:i+2])
		i+=2

		return {'flags': bin(flags), 'cmd_buffer': repr(cmd), 'checksum_errors': checksum_errors, 'send_buffer': repr(send), 'receive_buffer': repr(receive), 'send_cursor':send_cursor, 'transmitted_cursor': transmitted_cursor}

	@param('element_size', 'integer', 'positive', desc='Size of each flashqueue element [1, 256]')
	@param('subsections', 'integer', 'positive', desc='Number of subsections to allocate [2, 7]')
	@param('version', 'integer', 'positive', desc='Version of flashblock to create')
	def test_fq_init(self, element_size, subsections, version):
		self.rpc(42, 0x30, version, element_size, subsections)

	@return_type("integer")
	def test_fq_address(self):
		res = self.rpc(42, 0x32, result_type=(1, False))
		return res['ints'][0]

	@param("start", 'integer')
	@param("count", 'integer')
	def test_fq_push_n(self, start, count):
		self.rpc(42, 0x31, count, start, timeout=20.0)

	@return_type("integer")
	def test_fq_pop(self):
		res = self.rpc(42, 0x33, result_type=(1, True))

		if res['ints'][0] == 0:
			return -1

		out = ord(res['buffer'][0]) | (ord(res['buffer'][1]) << 8)
		return out
		
	@return_type("integer")
	@param("message", "string", desc="Message to send with broadcast packets (<=20 bytes)")
	def bt_setbroadcast(self, message):
		"""
		Set the message sent with broadcast packets for this device.

		The message needs to be <= 20 bytes long.  The call returns a
		status code from the BTLE module indicating success or failure.

		A return value of 0 is success.
		"""

		if len(message) > 20:
			raise ArgumentError("Message too long (limit = 20 bytes)", message=message)

		res = self.rpc(42, 0x28, message, result_type=(1, False))

		return res['ints'][0]

	@param("address", "integer", desc="Address of Comm Module to test")
	def test_comm_streaming(self, address):
		"""
		Stream a test message to the specified comm module
		"""

		res = self.rpc(60, 0x15, address)

	def momo_attached(self):
		resp, result = self.stream.send_cmd("attached")
		if result != CMDStream.OkayResult:
			raise RuntimeError("Attached command failed")

		resp = resp.lstrip().rstrip()
		val = int(resp)

		if val == 1:
			return True
		elif val == 0:
			return False
		else:
			raise RuntimeError("Invalid result returned from 'attached' command: %s" % resp)

	def sensor_log( self, stream, meta, value):
		res = self.rpc( 70, 0, stream, meta, struct.pack( 'Q', value ) );

	def sensor_log_read( self ):
		res = self.rpc( 70, 0x1, result_type=(0, True) )
		return SensorEvent( res['buffer'] )

	def sensor_log_count( self ):
		res = self.rpc( 70, 0x2, result_type=(0, True) )
		(count, ) = struct.unpack('I', res['buffer'])
		return count

	def sensor_log_clear( self ):
		res = self.rpc( 70, 0x3 )

	def sensor_log_debug( self ):
		res = self.rpc( 70, 0x4, result_type=(0, True) )
		(min, max, start, end) = struct.unpack('IIII', res['buffer'])
		return (min,max,start,end)

	@return_type('string')
	def get_report_interval(self):
		intervals = {4: '10 minutes', 5: '1 hour', 6: '1 day'}

		res = self.rpc(60, 0x04, result_type=(1,False))
		interval = res['ints'][0]

		if interval not in intervals:
			raise HardwareError("Unknown interval number in momo", interval=interval, known_intervals=intervals.keys())

		return intervals[interval]

	@param("interval", "string", desc="reporting interval")
	def set_report_interval(self, interval):
		"""
		Set the interval between automatic reports

		Interval should be passed as a string with valid options being:
		10 minutes
		1 hour
		1 day
		"""

		intervals = {'10 minutes': 4, '1 hour': 5, '1 day': 6}

		interval = interval.lower()

		if interval not in intervals:
			raise ValidationError("Unknown interval string", interval=interval, known_intervals=intervals.keys())

		intnumber = intervals[interval]

		self.rpc(60, 3, intnumber)

		value = self.get_report_interval()
		assert value == interval

	@annotated
	def start_reporting(self):
		"""
		Start regular reporting
		"""
		self.rpc(60, 1)

	@annotated
	def stop_reporting(self):
		"""
		Stop regular reporting
		"""
		self.rpc(60, 2)

	@return_type("bool")
	def reporting_state(self):
		"""
		Get whether automatic reporting is enabled
		"""

		res = self.rpc(60, 14, result_type=(1, True))
		enabled = bool(res['ints'][0])
		return enabled

	@annotated
	def reset_reporting_config(self):
		"""
		Reset the reporting configuration.
		"""
		res = self.rpc(60,0x12)

	@annotated
	def post_single_report(self):
		"""
		Send a single report
		"""

		self.rpc(60, 0)

	@param("index", "integer", desc="0 for primary route, 1 for secondary route")
	@param("route", "string", desc="URL or phone number to stream data to")
	def set_report_route(self, index, route):
		if len(route) == 0:
			arg = struct.unpack('H', struct.pack('BB', 0, int(index)))
			self.rpc(60, 5, arg[0], route)
		else:
			for i in xrange(0, len(route), 18):
				buf = route[i:i+18]
				arg = struct.unpack('H', struct.pack('BB', int(i), int(index)))
				self.rpc(60, 5, arg[0], buf)

	@param("index", "integer", desc="0 for primary route, 1 for secondary route")
	@return_type("string")
	def get_report_route(self, index):
		route = ""
		i = 0
		while True:
			arg = struct.unpack('H', struct.pack('BB', int(i),int(index)))
			res = self.rpc(60, 6, arg[0], result_type=(0, True))
			if len(res['buffer']) == 0:
				break
			i += len(res['buffer']);
			route += res['buffer']
		return route

	@return_type("string")
	def get_gprs_apn(self):
		res = self.rpc(60, 0x14, result_type=(0,True))
		return res['buffer']

	@param("apn", "string", desc='APN for gsm data connections')
	def set_gprs_apn(self, apn):
		res = self.rpc(60, 0x13, apn)

	@annotated
	@returns(desc="Time", data=True)
	def current_time(self):
		"""
		Get the current time according to the controller's RTCC
		"""

		res = self.rpc(42, 0x0C, result_type=(0, True));
		year, month, day, hour, minute, second = struct.unpack( "HHHHHH", res['buffer'] )

		return datetime( year+2000, month, day, hour, minute, second )

	@annotated
	def set_time(self, year, month, day, hours, minutes, seconds, weekday=0 ):
		"""
		Set the current time of the controller's RTCC
		"""

		packed = struct.pack('BBBBBBBB', int(year), int(month), int(day), int(hours), int(minutes), int(seconds), int(weekday), 0);
		self.rpc(42, 0x12, packed)

	@annotated
	def sync_time(self):
		"""
		Set the time on the momo controller to the current system time.
		"""

		#Module time should be in UTC so there is uniformity on the server side
		now = datetime.utcnow()
		self.set_time(now.date().year - 2000, now.date().month, now.date().day, now.time().hour, now.time().minute, now.time().second, now.weekday())
		print "Assigned UTC Time:", now

	@annotated
	def build_report(self):
		res = self.rpc(60, 0x0C)

	@annotated 
	def get_report(self):
		report = ""
		for i in xrange(0, 160, 20):
			res = self.rpc(60, 0x0D, i, result_type=(0, True))
			report += res['buffer']

		print report

	@param('counter', 'integer', 'nonnegative')
	@returns(desc="Performance Counter", printer=lambda x: x.display(), data=True)
	def perf_counter(self, counter):
		res = self.rpc(42, 0x26, counter, result_type=(0, True))
		return PerformanceCounter(res['buffer'], name=counter)

	@param('address', 'integer', 'nonnegative', desc='address to start reading')
	@param('type', 'string', desc='format read data as this type')
	@param('size', 'integer', 'nonnegative', desc='optional size of data to read')
	@returns(desc='read object')
	def read_ram(self, address, type=None, size=0):
		"""
		Read bytes from the controller ram starting at the specified address.  If a 
		type is provided, use the type information to determine how many bytes to read
		and how to format the results.  If type is supplied, an object of that type is
		returned. Otherwise read size bytes are read and returned as a binary string
		object.
		"""

		if type is not None:
			if not typedargs.type_system.is_known_type(type):
				raise ArgumentError("unknown type specified", type=type)

			if size == 0:
				size = typedargs.type_system.get_type_size(type)

		if size == 0:
			raise ArgumentError("size not specified and could not be determined from supplied type info", supplied_size=size, supplied_type=type)

		buf = ""

		for i in xrange(0, size, 20):
			res = self.rpc(42, 0x11, address+i, result_type=(0, True))
			valid = min(20, size - i)
			buf += res['buffer'][:valid]
		
		if size != len(buf):
			raise InternalError("Read size does not match specified size, this should not happen", read_size=len(buf), specified_size=size)
		
		if type is not None:
			return typedargs.type_system.convert_to_type(buf, type)

		return buf

	@return_type("integer")
	def scheduler_map(self):
		"""
		Get the map of used scheduler buckets
		"""

		res = self.rpc(43, 2, result_type=(1, False));

		return res['ints'][0];

	def scheduler_new(self, address, feature, command, frequency):
		"""
		Schedule a new task
		"""

		res = self.rpc(43, 0, int(address), ( (int(feature)<<8) | (int(command)&0xFF) ), int(frequency) );

	def scheduler_remove(self, address, feature, command, frequency):
		"""
		Remove a scheduled task
		"""

		res = self.rpc(43, 1, int(address), ( (int(feature)<<8) | (int(command)&0xFF) ), int(frequency) );

	@return_type('map(string, integer)')
	def scheduler_describe(self, index):
		"""
		Describe a scheduled callback
		"""

		try:
			res = self.rpc(43, 3, int(index), result_type=(0,True) );
			return struct.unpack('BBBxB', res['buffer'][:5])
		except RPCException as e:
			if e.type == 7:
				return None

	@annotated
	def reset(self, sync=True):
		"""
		Instruct the controller to reset itself.
		"""

		try:
			self.rpc(42, 0xF)
		except ModuleNotFoundError:
			pass

		if sync:
			sleep(1.5)

	@annotated
	@returns(desc="Module UUID", printer=_print, data=True)
	def uuid(self):
		"""
		Get the current UUID of the controller.
		"""

		res = self.rpc(42, 0x13, result_type=(2,False))
		guid = struct.pack('HH', res['ints'][0], res['ints'][1])
		print struct.unpack('<L', guid)[0];
		return base64.b64encode(bytes(guid)).rstrip('=')

	@annotated 
	def register(self):
		#TODO: register with the server
		guid = uuid.uuid4()
		guid = struct.unpack('<L', guid.bytes[-4:])[0]
		print guid
		print base64.b64encode(struct.pack('<L', guid)).rstrip('=')
		self.rpc(42, 0x14, guid & 0xFFFF, guid >> 16)

	@annotated
	def factory_reset(self):
		"""
		Instruct the controller to reset all internal state to "factory defaults."  Use with caution.
		"""
		self.rpc(42, 0x10)