import proxy
from pymomo.cmdr.exceptions import *
from pymomo.cmdr.types import *
from pymomo.utilities.console import ProgressBar
import struct
from intelhex import IntelHex

class MIBController (proxy.MIBProxyObject):
	def __init__(self, stream):
		super(MIBController, self).__init__(stream, 8)
		self.name = 'Controller'

	def count_modules(self):
		"""
		Count the number of attached devices to this controller
		"""

		res = self.rpc(42, 1, result_type=(1, False))
		return res['ints'][0]

	def describe_module(self, index):
		"""
		Describe the module given its module index
		"""
		res = self.rpc(42, 2, index, result_type=(0,True))

		return ModuleDescriptor(res['buffer'], 11+index)

	def get_module(self, by_name=None, by_address=None, force=False):
		"""
		Given a module name or a fixed address, return a proxy object
		for that module if it is connected to the bus.  If force is True
		this call will construct an proxy object for the given address even
		if the module is not found in the controller's database of connected
		modules.
		"""

		if by_address is not None and force:
			obj = proxy.MIBProxyObject(self.stream, by_address)
			obj.name = 'Unknown'
			return obj

		mods = self.enumerate_modules()
		if by_name is not None and len(by_name) < 7:
			by_name += (' '*(7 - len(by_name)))

		for mod in mods:
			if by_name == mod.name or by_address == mod.address:
				obj = proxy.MIBProxyObject(self.stream, mod.address)
				obj.name = mod.name
				return obj

		raise ValueError("Could not find module by name or address (name=%s, address=%s)" % (str(by_name), str(by_address)))

	def enumerate_modules(self):
		"""
		Get list of all attached modules and describe them all
		"""
		
		num = self.count_modules()

		mods = []

		for i in xrange(0, num):
			mods.append(self.describe_module(i))

		return mods

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
		cnt = self.get_firmware_count()

		if bucket >= cnt:
			raise ValueError("Invalid firmware bucket specified, only %d buckets are filled" % cnt)

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

			prog.progress(i//20)

		prog.end()

		return out

	def get_firmware_count(self):
		res = self.rpc(7, 5, result_type=(1, False))
		return res['ints'][0]

	def clear_firmware_cache(self):
		self.rpc(7, 0x0A)

	def get_firmware_info(self, bucket):
		"""
		Get the firmware size and module type stored in the indicated bucket
		"""

		res = self.rpc(7, 3, bucket, result_type=(3, False))

		length = res['ints'][1] << 16 | res['ints'][2]
		return {'module_type': res['ints'][0], 'length': length}

	def get_firmware_count(self):
		"""
		Get the number of firmware buckets currently occupied
		"""

		res = self.rpc(7, 5, result_type=(1, False))
		return res['ints'][0]