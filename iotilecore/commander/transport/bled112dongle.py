# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from iotilecore.commander.exceptions import *
from iotilecore.exceptions import HardwareError, TimeoutError, ArgumentError
from cmdstream import CMDStream
from iotilecore.utilities.asyncio import AsyncPacketBuffer
from iotilecore.commander.commands import RPCCommand
import serial
import sys
from collections import namedtuple, deque
import time
import base64
import random
import time
import struct
import itertools
import uuid
from iotilecore.utilities.packed import unpack

def packet_length(header):
	"""
	Find the BGAPI packet length given its header
	"""

	highbits = header[0] & 0b11
	lowbits = header[1]

	return (highbits << 8) | lowbits

BGAPIPacket = namedtuple("BGAPIPacket", ["is_event", "command_class", "command", "payload"])
CharacteristicProperties = namedtuple("CharacteristicProperties", ["broadcast", "read", "write_no_response", "write", "notify", "indicate", "write_authenticated", "extended"])

class BLED112Dongle:
	"""
	Python wrapper around the BlueGiga BLED112 bluetooth dongle
	"""

	#FIXME: There's an endianness issue here where the byte order of the uuid's seem wrong in LSB positions
	MLDPService = uuid.UUID('3a0003000812021add07e658035b0300')
	MLDPDataCharacteristic = uuid.UUID('3a0003010812021add07e658035b0300')
	TileBusService = uuid.UUID('0ff60f63-132c-e611-ba53-f73f00200000')
	TileBusSendHeaderCharacteristic = uuid.UUID('fb349b5f-8000-0080-0010-000000000320')
	TileBusSendPayloadCharacteristic = uuid.UUID('fb349b5f-8000-0080-0010-000000000420')
	TileBusReceiveHeaderCharacteristic = uuid.UUID('fb349b5f-8000-0080-0010-000000000120')
	TileBusReceivePayloadCharacteristic = uuid.UUID('fb349b5f-8000-0080-0010-000000000220')
	TileBusStreamingCharacteristic = uuid.UUID('fb349b5f-8000-0080-0010-000000000520')


	def __init__(self, port, ):
		self.io = serial.Serial(port=port, timeout=None, rtscts=True)
		self.io.flushInput()

		self.stream = AsyncPacketBuffer(self.io, header_length=4, length_function=packet_length, oob_function=self._check_process_streaming_data)
		self.events = deque()
		self.stream_enabled = False

	def _get_streaming_queue(self):
		"""
		Get the queue that will contained any streamed readings that have been sent
		"""

		return self.stream.oob_queue

	def _check_process_streaming_data(self, response_data):
		packet = BGAPIPacket(is_event=(response_data[0] == 0x80), command_class=response_data[2], command=response_data[3], payload=response_data[4:])

		if not self.stream_enabled:
			return None

		if packet.is_event and packet.command_class == 4 and packet.command == 5:
			handle, value = self._process_notification(packet)
			#FIXME: this hardcored value should instead be read once the device is probed so that it is correct 
			#if the GATT server db ever changes
			if handle == 21:
				return value

		return None

	def _send_command(self, cmd_class, command, payload, timeout=3.0, force_length=None, print_packet=False):
		"""
		Send a BGAPI packet to the dongle and return the response
		"""

		if len(payload) > 60:
			return DataError("Attempting to send a BGAPI packet with length > 60 is not allowed", actual_length=len(payload), command=command, command_class=cmd_class)

		header = bytearray(4)
		header[0] = 0

		if force_length is None:
			header[1] = len(payload)
		else:
			header[1] = force_length
		header[2] = cmd_class
		header[3] = command

		packet = header + bytearray(payload)
		if print_packet:
			print ':'.join([format(x, "02X") for x in packet])
		
		self.io.write(packet)

		#Every command has a response so wait for the response here
		response = self._receive_packet(timeout)
		return response

	def _receive_packet(self, timeout=3.0):
		"""
		Receive a response packet to a command, automatically storing any events that may have
		occurred before the response is received
		"""

		while True:
			response_data = self.stream.read_packet(timeout=timeout)
			response = BGAPIPacket(is_event=(response_data[0] == 0x80), command_class=response_data[2], command=response_data[3], payload=response_data[4:])

			if response.is_event:
				self.events.append(response)
				continue

			return response

	def _accumulate_events(self, timeout=3.0):
		"""
		Wait for any events that might occur in a fixed period of time
		"""

		start = time.clock()
		end = start + timeout

		events = []

		try:
			while True:
				remaining = end - time.clock()

				if remaining < 0:
					break

				response_data = self.stream.read_packet(timeout=remaining)
				response = BGAPIPacket(is_event=(response_data[0] == 0x80), command_class=response_data[2], command=response_data[3], payload=response_data[4:])

				if not response.is_event:
					raise InternalError("A BGAPI response was received during a period where only events should have been received", response=response)

				events.append(response)
		except TimeoutError:
			pass

		return events

	def _accumulate_until(self, cmdclass, method, timeout=3.0):
		"""
		Accumulate events until a specific event happens and return all the events received.

		If the final event does not happen in the timeout window, raise a TimeoutError
		"""

		start = time.clock()
		end = start + timeout

		events = []

		while True:
			remaining = end - time.clock()

			if remaining < 0:
				break

			response_data = self.stream.read_packet(timeout=remaining)
			response = BGAPIPacket(is_event=(response_data[0] == 0x80), command_class=response_data[2], command=response_data[3], payload=response_data[4:])

			if not response.is_event:
				raise InternalError("A BGAPI response was received during a period where only events should have been received", response=response)

			if response.command_class == cmdclass and response.command == method:
				return events, response
			else:
				events.append(response)

	def _wait_for_event(self, cmdclass, method, timeout=5.0):
		start = time.clock()
		end = start + timeout

		while True:
			remaining = end - time.clock()

			if remaining < 0:
				raise TimeoutError()

			response_data = self.stream.read_packet(timeout=remaining)
			response = BGAPIPacket(is_event=(response_data[0] == 0x80), command_class=response_data[2], command=response_data[3], payload=response_data[4:])

			if not response.is_event:
				raise InternalError("A BGAPI response was received during a period where only events should have been received", response=response)

			if response.command_class == cmdclass and response.command == method:
				return response

	def _set_scan_parameters(self, interval=2100, window=2100, active=False):
		"""
		Set the scan interval and window in units of ms and set 
		whether active scanning is performed
		"""

		active_num = 0
		if bool(active):
			active_num = 1

		interval_num = int(interval*1000/625)
		window_num = int(window*1000/625)

		payload = struct.pack("<HHB", interval_num, window_num, active_num)

		response = self._send_command(6, 7, payload)
		if response.payload[0] != 0:
			raise HardwareError("Could not set scanning parameters", error_code=response.payload[0], response=response)

	def _parse_scan_response(self, response):
		payload = response.payload
		length = len(payload) - 10

		if length < 0:
			raise HardwareError("Invalid scan response packet length", length=len(payload), min_length=10)

		rssi, packet_type, sender, addr_type, bond, data = unpack("<bB6sBB%ds" % length, payload)

		parsed ={}
		parsed['rssi'] = rssi
		parsed['type'] = packet_type
		parsed['address_raw'] = sender
		parsed['address'] = ':'.join([format(ord(x), "02X") for x in sender[::-1]])
		parsed['address_type'] = addr_type 
		
		#Scan data is prepended with a length
		if len(data)  > 0:
			parsed['scan_data'] = bytearray(data[1:])
		else:
			parsed['scan_data'] = bytearray([])

		return parsed

	def scan(self, timeout=4.0):
		"""
		Scan for BLE devices for a fixed period of time

		Return an entry all distinct btle devices that were found
		"""

		# Possible payloads are:
		# 0: only limited discoverable devices
		# 1: generic and limited discoverable devices
		# 2: all devices regardless of discoverability

		self._set_scan_parameters(active=False)

		response = self._send_command(6, 2, [2])
		if response.payload[0] != 0:
			raise HardwareError("Could not initiate scan for ble devices", error_code=response.payload[0], response=response)

		
		scan_events = self._accumulate_events(timeout)
		scan_events = map(self._parse_scan_response, scan_events)

		response = self._send_command(6, 4, [])
		if response.payload[0] != 0:
			raise HardwareError("Could not stop scanning for ble devices", error_code=response.payload[0], response=response)

		#Remove duplicate entries
		addrs = set()

		filtered_events = []
		for x in scan_events:
			if x['address'] in addrs:
				continue

			filtered_events.append(x)
			addrs.add(x['address'])

		return filtered_events

	def connect(self, address, timeout=4.0):
		latency = 0
		conn_interval_min = 6
		conn_interval_max = 100

		#Allow passing either a binary address or a hex string
		if isinstance(address, basestring) and len(address) > 6:
			address = address.replace(':', '')
			address = str(bytearray.fromhex(address)[::-1])

		#Allow simple determination of whether a device has a public or private address
		#This is not foolproof
		private_bits = ord(address[-1]) >> 6
		if private_bits == 0b11:
			address_type = 1
		else:
			address_type = 0

		payload = struct.pack("<6sBHHHH", address, address_type, conn_interval_min, conn_interval_max, int(timeout*100.0), latency)
		response = self._send_command(6, 3, payload)

		try:
			result, handle = unpack("<HB", response.payload)
		except:
			print type(response.payload)
			print response.payload
			print len(response.payload)
			raise

		if result != 0:
			raise HardwareError("Could not start connection", error_code=result)

		event = self._wait_for_event(0x03, 0, timeout)
		handle, flags, address, typevar, interval, timeout, latency, bonding = unpack("<BB6sBHHHB", event.payload)

		connection = {
		"handle": handle,
		"flags": flags,
		"address_raw": address,
		"interval": interval,
		"timeout": timeout,
		"latency": latency,
		"bonding": bonding
		}

		return connection

	def disconnect(self, connection, timeout=5.0):
		payload = struct.pack('<B', connection['handle'])
		response = self._send_command(3, 0, payload)

		handle, result = unpack("<BH", response.payload)

		if result != 0:
			raise HardwareError("Could not disconnect connection handle", handle=handle, error_code=result)

		event = self._wait_for_event(0x03, 0x04, timeout=5.0)
		return event

	def _enumerate_gatt_services(self, connection, type="primary", timeout=5.0):
		#Enumerate primary services
		if type == "primary":
			code = 0x2800
		elif type == "secondary":
			code = 0x2801
		else:
			raise ArgumentError("Unknown gatt service type, should be primary or secondary", type=type)

		payload = struct.pack('<BHHBH', connection['handle'], 1, 0xFFFF, 2, code)
		response = self._send_command(4, 1, payload)

		handle, result = unpack("<BH", response.payload)

		if result != 0:
			raise HardwareError("Could not enumerate gatt", handle=handle, error_code=result)

		events,end = self._accumulate_until(4, 1, timeout)
	
		services  = {}
		for event in events:
			self._process_gatt_service(services, event)		

		return services

	def _enumerate_handles(self, connection, start_handle, end_handle, timeout=5.0):
		"""
		Return a list of all of the defined handles on the remote device between two handle values
		"""

		payload = struct.pack("<BHH", connection['handle'], start_handle, end_handle)
		response = self._send_command(4, 3, payload)

		handle, result = unpack("<BH", response.payload)

		if result != 0:
			raise HardwareError("Could not enumerate handles", handle=handle, error_code=result)

		events,end = self._accumulate_until(4, 1, timeout)

		attrs = {}
		for event in events:
			self._process_attribute(attrs, event)

		return attrs

	def _process_attribute(self, attributes, event):
		length = len(event.payload) - 3
		handle, chrhandle, uuid = unpack("<BH%ds" % length, event.payload)
		uuid = self._process_uuid(uuid)
		
		attributes[chrhandle] = {'uuid': uuid}

	def _process_uuid(self, guiddata):
		guiddata = bytearray(guiddata)

		if len(guiddata) == 3 or len(guiddata) == 5 or len(guiddata) == 17:
			guiddata = guiddata[1:]

		if (not len(guiddata) == 2) and (not len(guiddata) == 16) and (not len(guiddata) == 4):
			raise ArgumentError("Invalid guid length, is not 2, 4 or 16", guid=guiddata)

		#Byte order is LSB first for the entire guid
		if len(guiddata) != 16:
			base_guid = uuid.UUID(hex="{FB349B5F8000-0080-0010-0000-00000000}").bytes_le
			base_guid = base_guid[:-len(guiddata)] + str(guiddata)

			return uuid.UUID(bytes_le=base_guid)

		return uuid.UUID(bytes_le=str(guiddata))

	def _process_gatt_service(self, services, event):
		length = len(event.payload) - 5

		handle, start, end, uuid = unpack('<BHH%ds' % length, event.payload)

		uuid = self._process_uuid(uuid)
		services[uuid] = {'uuid_raw': uuid, 'start_handle': start, 'end_handle': end}

	def _parse_characteristic_declaration(self, value):
		length = len(value)

		if length == 5:
			uuid_len = 2
		elif length == 19:
			uuid_len = 16
		else:
			raise ArgumentError("Value has improper length for ble characteristic definition", value_length=length, expected=[5, 19])

		propval, handle, uuid = unpack("<BH%ds" % uuid_len, value)


		#Process the properties
		properties = CharacteristicProperties(bool(propval & 0x1), bool(propval & 0x2), bool(propval & 0x4), bool(propval & 0x8), 
											  bool(propval & 0x10), bool(propval & 0x20), bool(propval & 0x40), bool(propval & 0x80))

		uuid = self._process_uuid(uuid)
		char = {}
		char['uuid'] = uuid
		char['properties'] = properties
		char['handle'] = handle

		return char

	def _process_read_data(self, event):
		length = len(event.payload) - 5
		conn, att_handle, att_type, act_length, value = unpack("<BHBB%ds" % length, event.payload)

		assert act_length == length

		return att_type, bytearray(value)

	def _process_notification(self, event):
		length = len(event.payload) - 5
		conn, att_handle, att_type, act_length, value = unpack("<BHBB%ds" % length, event.payload)

		assert act_length == length
		return att_handle, bytearray(value)

	def read_handle(self, conn, handle, timeout=5.0):
		payload = struct.pack("<BH", conn['handle'], handle)
		response = self._send_command(4, 4, payload)

		handle, result = unpack("<BH", response.payload)

		if result != 0:
			raise HardwareError("Could not enumerate handles", handle=handle, error_code=result)

		events, end = self._accumulate_until(4, 5, timeout)
		assert len(events) == 0

		return self._process_read_data(end)

	def write_handle(self, conn, handle, value, timeout=5.0, wait_ack=True):
		payload = struct.pack("<BHB%ds" % len(value), conn['handle'], handle, len(value), value)

		if wait_ack:
			response = self._send_command(4, 5, payload)
		else:
			response = self._send_command(4, 6, payload)

		handle, result = unpack("<BH", response.payload)

		if result != 0:
			raise HardwareError("Could not enumerate handles", handle=handle, error_code=result)

		if wait_ack:
			events, end = self._accumulate_until(4, 1, timeout)
			assert len(events) == 0

	def probe_device(self, conn, timeout=5.0):
		services = self._enumerate_gatt_services(conn, "primary", timeout)

		for uuid, service in services.iteritems():
			attributes = self._enumerate_handles(conn, service['start_handle'], service['end_handle'], timeout)

			service['characteristics'] = {}

			last_char = None
			for handle, attribute in attributes.iteritems():
				if attribute['uuid'].hex[-4:] == '0328':
					att_type, value = self.read_handle(conn, handle, timeout)
					char = self._parse_characteristic_declaration(value)
					
					service['characteristics'][char['uuid']] = char
					last_char = char
				elif attribute['uuid'].hex[-4:] == '0229':
					if last_char == None:
						raise HardwareError("Improper ordering of attribute handles, Client Characteristic preceeded all characteristic definitions", handle=handle)

					att_type, value = self.read_handle(conn, handle, timeout)
					assert len(value) == 2
					value, = unpack("<H", value)

					last_char['client_configuration'] = {'handle': handle, 'value': value}

		return services

	def check_mldp(self, services):
		if BLED112Dongle.MLDPService not in services:
			return False

		mldp = services[BLED112Dongle.MLDPService]

		if BLED112Dongle.MLDPDataCharacteristic not in mldp['characteristics']:
			return False

		return True

	def start_mldp(self, conn, services, version="v1"):
		if self.check_mldp(services) != True:
			raise HardwareError("MLDP does not exist on remote device")

		char = services[BLED112Dongle.MLDPService]['characteristics'][BLED112Dongle.MLDPDataCharacteristic]

		if version not in ['v1', 'v2']:
			raise ArgumentError("Unknown MLDP version", version=version, known_versions=['v1', 'v2'])

	def send_tilebus_packet(self, conn, services, address, feature, cmd, payload, **kwargs):
		header_char = services[BLED112Dongle.TileBusService]['characteristics'][BLED112Dongle.TileBusSendHeaderCharacteristic]
		payload_char = services[BLED112Dongle.TileBusService]['characteristics'][BLED112Dongle.TileBusSendPayloadCharacteristic]

		length = len(payload)

		if len(payload) < 20:
			payload += '\x00'*(20 - len(payload))

		if len(payload) > 20:
			raise ArgumentError("Payload is too long, must be at most 20 bytes", payload=payload, length=len(payload))

		header = chr(length) + chr(0) + chr(cmd) + chr(feature) + chr(address)

		if length > 0:
			self.write_handle(conn, payload_char['handle'], str(payload), wait_ack=False)
		
		self.write_handle(conn, header_char['handle'], str(header), wait_ack=False)
		
		timeout = 3.0
		if "timeout" in kwargs:
			timeout = kwargs['timeout']

		return self.receive_tilebus_response(conn, services, timeout)

	def receive_tilebus_response(self, conn, services, timeout=3.0):
		#Result of TileBus command is notified to us so wait for the notification
		events, end = self._accumulate_until(4, 5, timeout)
		assert len(events) == 0

		handle, value = self._process_notification(end)

		status = value[0]
		length = value[3]

		if length > 0:
			payload_char = services[BLED112Dongle.TileBusService]['characteristics'][BLED112Dongle.TileBusReceivePayloadCharacteristic]
			events, end = self._accumulate_until(4, 5, timeout)
			assert len(events) == 0
			handle, payload = self._process_notification(end)
			assert handle == payload_char['handle']
		else:
			payload = '\x00'*20

		complete_response = bytearray(value) + bytearray(payload) + bytearray('\x00') #Append a dummy checksum
		return str(complete_response)

	def send_mib_packet(self, conn, services, address, feature, cmd, payload, **kwargs):
		char = services[BLED112Dongle.MLDPService]['characteristics'][BLED112Dongle.MLDPDataCharacteristic]

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

		out_buffer = str(out_buffer)

		self.write_handle(conn, char['handle'], out_buffer[:20])
		self.write_handle(conn, char['handle'], out_buffer[20:])
		#self.write_handle(conn, char['handle'], out_buffer[21:])

		timeout = 3.0
		if "timeout" in kwargs:
			timeout = kwargs['timeout']

		return self.receive_mib_response(timeout)

	def receive_mib_response(self, timeout=3.0):
		received = ""
		while len(received) < 40:
			events, end1 = self._accumulate_until(2, 0, timeout)
			assert len(events) == 0

			data = str(end1.payload[7:])
			received += data

		#Chomp the \r\n from the end of the response
		if received[-2:] == '\r\n':
			received = received[:-2]

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

	def set_notification(self, conn, char, enabled, timeout=5.0):
		if 'client_configuration' not in char:
			raise ArgumentError("Cannot enable notification without a client configuration attribute for characteristic", characteristic=char)

		props = char['properties']
		if not props.notify:
			raise ArgumentError("Canot enable notification on a characteristic that does not support it", characteristic=char)

		value = char['client_configuration']['value']

		#Check if we don't have to do anything
		current_state = bool(value & (1 << 0))
		if current_state == enabled:
			return

		if enabled:
			value |= 1 << 0
		else:
			value &= ~(1 << 0)

		char['client_configuration']['value'] = value

		valarray = struct.pack("<H", value)
		self.write_handle(conn, char['client_configuration']['handle'], valarray, timeout)

	def set_indication(self, conn, char, enabled, timeout=5.0):
		if 'client_configuration' not in char:
			raise ArgumentError("Cannot enable indication without a client configuration attribute for characteristic", characteristic=char)

		props = char['properties']
		if not props.indicate:
			raise ArgumentError("Canot enable indication on a characteristic that does not support it", characteristic=char)

		value = char['client_configuration']['value']

		#Check if we don't have to do anything
		current_state = bool(value & (1 << 1))
		if current_state == enabled:
			return

		if enabled:
			value |= 1 << 1
		else:
			value &= ~(1 << 1)

		char['client_configuration']['value'] = value

		valarray = struct.pack("<H", value)
		self.write_handle(conn, char['client_configuration']['handle'], valarray, timeout)