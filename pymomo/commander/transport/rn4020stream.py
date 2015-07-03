from pymomo.commander.exceptions import *
from pymomo.exceptions import HardwareError, TimeoutError
from cmdstream import CMDStream
from pymomo.utilities.asyncio import AsyncLineBuffer
from pymomo.commander.commands import RPCCommand
import serial
import sys
from collections import namedtuple
import time
import base64

BTLECharacteristic = namedtuple("BTLECharacteristic", ["value_handle", "readable", "writable", "config_handle", "notify", "indicate"])

class RN4020SerialBoard:
	MIBService = "7B497847C57449B09F1809D9B4A6FFCD"
	MIBResponseCharacteristic = "B809532DD80F47CEB27D36A393F90508"
	MIBResponsePayloadCharacteristic = "9E7651BEFE854CCC819F8700C5D94D8F"
	MIBCommandCharacteristic = "4041BBD45344409293297BECBD38A1CE"
	MIBPayloadCharacteristic = "4D3A77E2F53447B78E659466BB9BA209"

	def __init__(self, port):
		self.io = serial.Serial(port=port, baudrate=115200, timeout=None, rtscts=True)
		time.sleep(0.1) #Sometimes a single bad character gets sent upon startup
		self.io.flushInput()

		self.stream = AsyncLineBuffer(self.io, separator='\r\n')

		self.payload = []
		self.payload_stamp = 0
		self.response = []
		self.response_stamp = 0
		self.connected = False
		self.mldp_mode = False

		self.check_centrality()

	def check_centrality(self):
		"""
		Make sure that we're configured for central mode, not peripheral
		"""

		self.io.write("GR\n")
		res = self.receive_solicited()

		mode = int(res, 16)
		
		if mode != 0x92000000:
			self.io.write("SR,92000000\n")
			res = self.receive_solicited()
			if res != 'AOK':
				raise HardwareError("Could not set RN4020 to central mode")

			self.reboot()

	def receive_solicited(self, timeout=3.0, include_connection=False):
		done = False
		while True:
			line = self.stream.readline(timeout)
			if line.startswith("WV,") or line.startswith("WC,") or line.startswith("Notify,") or line.startswith("Indicate,") or line.startswith("ConnParam:"):
				#FIXME: process this and update our stuff
				print line
			elif line == 'Connection End':
				self.connected = False
				if include_connection:
					return line
			else:
				return line

	def await_notification(self, timeout=3.0):
		while True:
			line = self.stream.readline(timeout)
			if line.startswith("Notify,") or line.startswith("Indicate,"):
				return line

	def reboot(self):
		self.io.write("R,1\n")

		rb = self.receive_solicited()
		if rb != "Reboot":
			raise HardwareError("Invalid response to command from RN4020", command="R,1", response=rb)

		cmd = self.receive_solicited()
		if cmd != '\x00CMD':
			raise HardwareError("Invalid response to command from RN4020", command="R,1", response=cmd)

	def read(self, char_uuid):
		"""
		Read the remote service characteristic
		"""

		handle = self.services[RN4020SerialBoard.MIBService][char_uuid]['value_handle']
		cmd = "CHR,%s\n" % handle

		self.io.write(cmd)
		r = self.receive_solicited()
		
		if r.startswith("ERR"):
			code = r[4:-1]
			raise HardwareError("Could not read characteristic", uuid=char_uuid, error_code=int(code, 16))

		hexbytes = r[2:-1]

		if len(hexbytes) % 2 != 0:
			raise HardwareError("Invalid read data with length not a multiple of 2", length=len(hexbytes), response=r)

		out = bytearray(len(hexbytes)/2)
		for i in xrange(0, len(hexbytes), 2):
			out[i/2] = int(hexbytes[i:i+1], 16)

		return out

	def write(self, char_uuid, value):
		if not self.connected:
			raise HardwareError("Cannot write without being connected")

		handle = self.services[RN4020SerialBoard.MIBService][char_uuid]['value_handle']

		packed_value = ""
		for i in xrange(0, len(value)):
			packed_value += (hex(value[i])[2:].upper())

		cmd = "CHW,%s,%s\n" % (handle, packed_value)
		self.io.write(cmd)

		r = self.receive_solicited()
		if r == 'AOK':
			return

		raise HardwareError("Could not write value to characteristic", response=r)

	def enter_mldp(self):
		if self.mldp_mode:
			return

		if not self.connected:
			raise HardwareError("Cannot enter MLDP mode until we are connected")

		self.io.write("I\n")
		r = self.receive_solicited()

		if r != 'MLDP':
			raise HardwareError("Could not enter MLDP mode")

		self.mldp_mode = True

	def leave_mldp(self):
		if self.mldp_mode == False:
			return

		if not self.connected:
			return

		time.sleep(1.2)
		self.io.write('$$$\r')
		time.sleep(0.05)
		self.io.write('I#A,04\r')
		time.sleep(0.1)
		self.io.write('I#A,00\r')
		time.sleep(1.2)
		self.io.write('$$$\r')
		time.sleep(0.1)
		
		#self.io.write('GN\r')
		
		time.sleep(0.2)
		while self.stream.available() > 0:
			print self.stream.readline(3.0)

		self.mldp_mode = False

	def get_connection_params(self):
		self.io.write("GT\n")
		return self.receive_solicited()

	def test_throughput(self, trials=100):
		"""
		Determine how many commands can be executed per second
		"""

		self.enter_mldp()
		payload = bytearray(23)
		
		start = time.time()

		try:
			for i in xrange(0, trials):

				val = '@' + base64.b64encode(payload) + chr(ord('0') + (i % 100)/10) + chr(ord('0') + i%10) + '!\r\n'
				self.io.write(val)
				r = self.receive_solicited()

				if r != val[1:-2]:
					print "Invalid response echoed back"
					print repr(r)
					break
		except TimeoutError:
			print "Error occurred after %d trials" % i

		end = time.time()

		print start
		print end
		return trials/(end - start)*20

	def enable_notifiations(self, uuid):
		"""
		Enable notifications on the remote characteristic specified by the given uuid
		"""

		if not self.connected:
			raise HardwareError("Cannot enable notifications without being connected")

		service = self.services
		mib_service = service[RN4020SerialBoard.MIBService]

		if uuid not in mib_service:
			raise ArgumentError("Unknown characteristic", known_uuids=mib_service.keys(), given_uuid=uuid)

		char = mib_service[uuid]
		if char['notify'] == False:
			raise ArgumentError("Characteristic does not support notifications")

		cmd = "CHW,%s,0100\n" % char['config_handle']
		self.io.write(cmd)
		r = self.receive_solicited()
		if r != 'AOK':
			raise HardwareError("Error received enabling notifications", message=r)

	def connect(self, mac, timeout=5.0):
		cmd = "E,0,%s\n" % mac

		self.io.write(cmd)
		r = self.receive_solicited()
		if r != 'AOK':
			raise HardwareError("Error received from connection command", message=r)

		try:
			r = self.receive_solicited(timeout)
			if r != 'Connected':
				raise HardwareError("Connection could not be established for an unknown reason", message=r)
		except TimeoutError:
			raise HardwareError("Connection could not be established, attempt timed out.")

		self.connected = True
		self.peripheral_mac = mac

		services = self.list_services()
		if not self._check_mib(services):
			self.disconnect()
			raise HardwareError("Connection established but remote device does not support MIB service", supported_services=services)

		self.services = services
		self.enable_notifiations(RN4020SerialBoard.MIBResponseCharacteristic)

	def disconnect(self, throw=False):
		"""
		Disconnect from a peripheral device

		unless throw is True, eat any errors from this call since we may have already been disconnected 
		from the far side previously through a timeout.
		"""

		self.io.write('K\n')
		line = self.receive_solicited(include_connection=True)
		if line == 'Connection End':
			return
		elif line == 'ERR':
			if not throw:
				return

			raise HardwareError("Error received disconnecting from remote peripheral")
		
		raise HardwareError("Unknown response received from RN4020", response=line)

	def _check_mib(self, services):
		if RN4020SerialBoard.MIBService not in services:
			return False

		mib = services[RN4020SerialBoard.MIBService]

		if RN4020SerialBoard.MIBResponseCharacteristic not in mib:
			return False
		if RN4020SerialBoard.MIBResponsePayloadCharacteristic not in mib:
			return False
		if RN4020SerialBoard.MIBCommandCharacteristic not in mib:
			return False
		if RN4020SerialBoard.MIBPayloadCharacteristic not in mib:
			return False

		return True

	def list_services(self):
		if not self.connected:
			raise HardwareError("Cannot list services without being connected to a BTLE device")

		self.io.write("LC\n")

		lines = []

		while True:
			line = self.receive_solicited()
			if line == 'END':
				break

			lines.append(line)

		services = {}
		curr_service = None
		for line in lines:
			if line.startswith('  '):
				line = line[2:]
				uuid,handle,mode = line.split(',')

				mode = int(mode,16)

				if uuid not in services[curr_service]:
					services[curr_service][uuid] = {'notify': False, 'indicate': False, 'config_handle': None}

				if mode >= 0x10:
					notify = bool(mode & (1 << 4))
					indicate = bool(mode & (1 << 5))
					config_handle = handle
					
					services[curr_service][uuid]['notify'] = notify
					services[curr_service][uuid]['indicate'] = indicate
					services[curr_service][uuid]['config_handle'] = config_handle
				else:
					readable = bool(mode & (1 << 1))
					writeable = bool(mode & (1 << 3))
					
					services[curr_service][uuid]['value_handle'] = handle
					services[curr_service][uuid]['readable'] = readable
					services[curr_service][uuid]['writeable'] = writeable
			else:
				curr_service = line
				services[line] = {}

		return services

	def search(self, timeout=5.0):
		self.io.write("F\n")
		res = self.receive_solicited()
		if res != 'AOK':
			raise HardwareError("Could not start scanning for BTLE devices", response=res)

		try:
			for i in xrange(0, 8):
				other = self.receive_solicited(timeout)

				res = other.split(',')
				if len(res) == 5:
					mac,private,name,uuids,rssi = res
				else:
					mac,private,rssi = res
					uuids = ""
					name = ""

				print "%s: %s (%s)" % (name, mac, rssi)
		except TimeoutError:
			pass

		self.io.write("X\n")
		res = self.receive_solicited(timeout)
		if res != 'AOK':
			raise HardwareError("Could not stop scanning for BTLE devices")
