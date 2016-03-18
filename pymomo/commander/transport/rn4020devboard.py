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
import random

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
		self.picmode = False
		self.remote_cmd = False

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

	def enter_picmode(self):
		if self.picmode:
			return

		time.sleep(1.2)
		self.io.write('$$$')
		r = self.receive_solicited()
		if r != "<PIC-CMD>":
			raise HardwareError("Could not enter PIC mode", expected='<PIC-CMD>', received=r)
		
		#Buffer should now contain 1 carrot

		self.picmode = True

	def leave_picmode(self):
		if not self.picmode:
			return

		time.sleep(1.2)
		self.io.write('$$$')
		r = self.receive_solicited()
		if r != '>':
			raise HardwareError("Could not leave PIC mode", expected='>', received=r)

		r = self.receive_solicited()
		if r != "<PIC-END>":
			raise HardwareError("Could not leave PIC mode", expected='(anything followed by)<PIC-END>', received=r)

		#The first command after leaving PIC mode always fails..., just clear it out
		#We have to send more than just a \n because \n are silently ignored when there is no other data
		time.sleep(0.2)
		self.io.write('GN\n')
		r = self.receive_solicited()

		self.picmode = False

	def leave_mldp(self):
		if not self.mldp_mode and not self.remote_cmd:
			return

		self.enter_picmode()

		cmd = 'I#A,04\r'
		for i in xrange(0, len(cmd)):
			self.io.write(cmd[i])
			time.sleep(.05)

		r = self.receive_solicited()
		if r != ">" + cmd[:-1]:
			raise HardwareError("Could not send command in PIC mode", cmd=cmd, response=r, expected_response=cmd)
		r = self.receive_solicited()
		if r != ">OK":
			raise HardwareError("Could not send command in PIC mode", cmd=cmd, response=r, expected_response="OK")
		
		time.sleep(0.1)

		cmd = 'I#A,00\r'
		for i in xrange(0, len(cmd)):
			self.io.write(cmd[i])
			time.sleep(.05)

		r = self.receive_solicited()
		if r != ">" + cmd[:-1]:
			raise HardwareError("Could not send command in PIC mode", cmd=cmd, response=r, expected_response=cmd)
		r = self.receive_solicited()
		if r != ">OK":
			raise HardwareError("Could not send command in PIC mode", cmd=cmd, response=r, expected_response="OK")

		self.leave_picmode()
			
		self.mldp_mode = False
		self.remote_cmd = False

	def get_connection_params(self):
		self.io.write("GT\n")
		return self.receive_solicited()

	def receive_mib_response(self, timeout=3.0):
		received = self.receive_solicited(timeout=timeout)

		if len(received) == 38:
			if received[0] == '@':
				received = received[1:]
			else:
				raise HardwareError("Corrupted MIB packet received from MoMo device", received_packet=received, length=len(received), expected_first_character='@')
		elif len(received) != 37:
			raise HardwareError("Corrupted MIB packet (invalid length) received from MoMo device", received_packet=received, length=len(received))

		if received[-1] != '!':
			raise HardwareError("Corrupted MIB packet (invalid termination character) received from MoMo device", received_packet=received)

		received = received[:-1]
		assert len(received) == 36

		unpacked = base64.decodestring(received)
		assert len(unpacked) == 25

		return unpacked

	def send_mib_packet(self, address, feature, cmd, payload, **kwargs):
		length = len(payload)

		if len(payload) < 20:
			payload += '\x00'*(20 - len(payload))

		if len(payload) > 20:
			raise ArgumentError("Payload is too long, must be at most 20 bytes", payload=payload, length=len(payload))

		#Send checksum as well
		out_data = chr(address) + chr(length) + chr(0) + chr(cmd) + chr(feature) + payload
		checksum = 0

		for i in xrange(0, len(out_data)):
			checksum += out_data[i]

		checksum %= 256
		checksum = (256 - checksum) % 256

		out_buffer = '@' + out_data + chr(checksum) + '!'
		assert len(out_buffer) == 28

		self.enter_mldp()
		self.io.write(out_buffer)

		timeout = 3.0
		if "timeout" in kwargs:
			timeout = kwargs['timeout']
		packet = self.receive_mib_response(timeout=timeout)
		return packet

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

	def connect(self, mac, timeout=15.0):
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
		#if not self._check_mib(services):
			#self.disconnect()
			#raise HardwareError("Connection established but remote device does not support MIB service", supported_services=services)

		self.services = services
		#self.enable_notifiations(RN4020SerialBoard.MIBResponseCharacteristic)

	def disconnect(self, throw=False):
		"""
		Disconnect from a peripheral device

		unless throw is True, eat any errors from this call since we may have already been disconnected 
		from the far side previously through a timeout.
		"""

		if self.mldp_mode:
			self.leave_mldp()
		elif self.remote_cmd:
			self.leave_remote_mode()

		#Now that we're guaranteed to be back in normal cmd mode
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

	def enter_remote_mode(self):
		if self.remote_cmd:
			return

		if not self.connected:
			raise HardwareError("Cannot enter remote mode with being connected to a remote device")

		if self.mldp_mode:
			self.leave_mldp()

		self.io.write("!,1\n")
		r = self.receive_solicited()
		if r != 'RMT_CMD':
			raise HardwareError('Could not enter Remote Command mode', expected='RMT_CMD', response=r)

		self.remote_cmd = True

	def leave_remote_mode(self):
		self.leave_mldp()

	def read_remote_script(self):
		if not self.remote_cmd:
			raise HardwareError("You must be in remote command mode to read remote scripts")

		self.io.write("LW\n")
		r = self.receive_solicited()
		if r.startswith("LW\n"):
			r = r[3:]

		if r == 'ERR':
			raise HardwareError("Could not read remote script", response=r)

		resp = ""
		while r != 'END':
			resp += r
			r = self.receive_solicited()

		return resp

	def stop_remote_script(self):
		if not self.remote_cmd:
			raise HardwareError("You must be in remote command mode to stop remote scripts")

		self.io.write('WP\n')
		r = self.receive_solicited()
		if r.startswith('WP\n'):	
			r = r[3:]

		if r != 'AOK':
			raise HardwareError('Error stopping remote script')

	def load_connection_script(self):
		script = "@PW_ON\nA,07D0\n|O,04,04\n@CONN\n|O,04,00\n@DISCON\nA,07D0\n|O,04,04\n"
		self.enter_remote_mode()
		self.load_remote_script(script)
		self.leave_remote_mode()

	def load_remote_script(self, script):
		if not self.remote_cmd:
			raise HardwareError("You must be in remote command mode to load remote scripts")

		#Stop any script activity
		self.io.write("WP\n")
		r = self.receive_solicited()
		if r.startswith('WP\n'):	
			r = r[3:]

		if r != 'AOK':
			raise HardwareError('Error stopping remote script')

		#Clear old script
		self.io.write("WC\n")
		r = self.receive_solicited()
		if r.startswith('WC\n'):	
			r = r[3:]

		if r != 'AOK':
			raise HardwareError('Error clearing remote script')

		self.io.write('WW\n')

		r = self.receive_solicited()
		if r.startswith('WW\n'):	
			r = r[3:]

		if r != 'AOK':
			raise HardwareError('Error loading remote script')

		lines = script.split('\n')

		sent = ''
		for line in lines:
			line = line.rstrip()
			if line == "":
				continue

			line += '\n'
			sent += line

			self.io.write(line)
			time.sleep(0.1)

		self.io.write('\x1b')
	
		sent += '\x1b'
		r = self.receive_solicited()
		if r != sent:
				raise HardwareError("Error inputting script", sent_script=repr(line), received_script=repr(r))

		r = self.receive_solicited()
		if r != 'END':
			raise HardwareError("Could not send script", response=repr(r))

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
