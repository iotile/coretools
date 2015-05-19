import proxy
import proxy12
from pymomo.commander.exceptions import *
from pymomo.commander.types import *
from pymomo.commander.cmdstream import *
from pymomo.utilities.console import ProgressBar
import struct
from pymomo.utilities.intelhex import IntelHex
from time import sleep
from datetime import datetime
from pymomo.syslog import RawLogEntry, SystemLog
from pymomo.utilities.typedargs.annotate import annotated,param,returns, context
from pymomo.utilities import typedargs
from pymomo.exceptions import *
import itertools
import base64
import uuid

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
	def __init__(self, stream):
		super(MIBController, self).__init__(stream, 8)
		self.name = 'Controller'

	@returns(desc='number of attached module', data=True)
	def count_modules(self):
		"""
		Count the number of attached devices to this controller
		"""

		res = self.rpc(42, 1, result_type=(1, False))
		return res['ints'][0]

	def reflash(self):
		try:
			self.rpc(42, 0xA)
		except RPCException as e:
			if e.type != 63:
				raise e

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

		for i in xrange(0, count):
			res = self.rpc(42, 0x22, i, 0, result_type=(0, True))
			try:
				log.append(RawLogEntry(res['buffer']))
			except ValidationError as e:
				print "FAILED TO PARSE A LOG ENTRY, %d entries discarded" % (count - i)
				break

		return SystemLog(log)

	@param("name", "string", desc="module name")
	@param("address", "integer", ("range", 11, 127), desc="modules address")
	def get_module(self, name=None, address=None, force=False):
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

		mods = self.enumerate_modules()
		if name is not None and len(name) < 7:
			name += (' '*(7 - len(name)))

		for mod in mods:
			if name == mod.name or address == mod.address:
				obj = proxy12.MIB12ProxyObject(self.stream, mod.address)
				obj.name = mod.name
				return obj

		raise ValueError("Could not find module by name or address (name=%s, address=%s)" % (str(name), str(address)))

	@returns(desc='list of attached modules', printer=print_module_list, data=True)
	def enumerate_modules(self):
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

	def battery_status(self):
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

	def pull_firmware(self, bucket, verbose=True, pic12=True):
		res, reason = self._firmware_bucket_loaded(bucket)

		if res == False:
			raise ValueError(reason)

		info = self.get_firmware_info(bucket)
		length = info['length']

		out = IntelHex()

		if verbose:
			print "Getting Firmware, size=0x%X" % length
			prog = ProgressBar("Transmission Progress", length // 20)
			prog.start()

		for i in xrange(0, length, 20):
			res = self.rpc(7, 4, bucket, i, result_type=(0, True))

			for j in range(0, len(res['buffer'])):
				out[i+j] = ord(res['buffer'][j])
				if pic12 and (j%2 != 0):
					out[i+j] &= 0x3F

			if verbose:
				prog.progress(i//20)

		if verbose:
			prog.end()

		return out

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

		resp, result = self.stream.send_cmd("alarm status")
		if result != CMDStream.OkayResult:
			raise RuntimeError("Alarm status command failed")

		resp = resp.lstrip().rstrip()
		val = int(resp)

		if val == 0:
			return True
		elif val == 1:
			return False
		else:
			raise RuntimeError("Invalid result returned from 'alarm status' command: %s" % resp)


	def set_alarm(self, asserted):
		"""
		Instruct the field service unit to assert or deassert the alarm line on the MoMo bus.
		"""

		if asserted:
			arg = "yes"
		else:
			arg = "no"

		cmd = "alarm %s" % arg

		resp, result = self.stream.send_cmd(cmd)
		if result != CMDStream.OkayResult:
			raise RuntimeError("Set alarm command failed")

	@returns(desc='bluetooth receive buffer', data=True)
	def bt_debug_log(self):
		"""
		Return the first 20 bytes of BTLE communication receive buffer.
		This contains the response to the last command sent to the unit.
		"""


		res = self.rpc(42, 0x27, result_type=(0,True))
		return str(res['buffer'])

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

	def start_reporting(self):
		"""
		Start regular reporting
		"""
		self.rpc(60, 1)

	def stop_reporting(self):
		"""
		Stop regular reporting
		"""
		self.rpc(60, 2)

	def get_reporting(self):
		"""
		Get regular reporting state
		"""
		res = self.rpc(60,14, result_type=(1, True))
		enabled = bool(res['ints'][0])
		return enabled

	def reset_reporting_config(self):
		"""
		Reset the reporting configuration.
		"""
		res = self.rpc(60,0x12)

	def send_report(self):
		"""
		Send a single report
		"""

		self.rpc(60, 0)

	def set_report_route(self, index, route):
		if len(route) == 0:
			arg = struct.unpack('H', struct.pack('BB', 0, int(index)))
			self.rpc(60, 5, arg[0], route)
		else:
			for i in xrange(0, len(route), 18):
				buf = route[i:i+18]
				arg = struct.unpack('H', struct.pack('BB', int(i), int(index)))
				self.rpc(60, 5, arg[0], buf)

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

	def get_gprs_apn(self):
		res = self.rpc(60, 0x14, result_type=(0,True))
		return res['buffer']

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

		now = datetime.now()
		self.set_time( now.date().year - 2000, now.date().month, now.date().day, now.time().hour, now.time().minute, now.time().second, now.weekday() )
		print now

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
			if not typedargs.is_known_type(type):
				raise ArgumentError("unknown type specified", type=type)

			if size == 0:
				size = typedargs.get_type_size(type)

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
			return typedargs.convert_to_type(buf, type)

		return buf

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
		except RPCException as e:
			if e.type != 63:
				raise e

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