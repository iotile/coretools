from pymomo.commander.exceptions import *
from pymomo.exceptions import HardwareError, TimeoutError
from cmdstream import CMDStream
from pymomo.utilities.asyncio import AsyncPacketBuffer
from pymomo.commander.commands import RPCCommand
import serial
import sys
from collections import namedtuple, deque
import time
import base64
import random

def packet_length(header):
	"""
	Find the BGAPI packet length given its header
	"""

	highbits = header[0] & 0b11
	lowbits = header[1]

	return (highbits << 8) | lowbits

BGAPIPacket = namedtuple("BGAPIPacket", ["is_event", "command_class", "command", "payload"])

class BLED112Dongle:
	"""
	Python wrapper around the BlueGiga BLED112 bluetooth dongle
	"""

	MIBService = "7B497847C57449B09F1809D9B4A6FFCD"
	MIBResponseCharacteristic = "B809532DD80F47CEB27D36A393F90508"
	MIBResponsePayloadCharacteristic = "9E7651BEFE854CCC819F8700C5D94D8F"
	MIBCommandCharacteristic = "4041BBD45344409293297BECBD38A1CE"
	MIBPayloadCharacteristic = "4D3A77E2F53447B78E659466BB9BA209"

	def __init__(self, port):
		self.io = serial.Serial(port=port, timeout=None, rtscts=True)
		self.io.flushInput()

		self.stream = AsyncPacketBuffer(self.io, header_length=4, length_function=packet_length)
		self.events = deque()

	def _send_command(self, cmd_class, command, payload, timeout=3.0):
		"""
		Send a BGAPI packet to the dongle and return the response
		"""

		if len(payload) > 60:
			return DataError("Attempting to send a BGAPI packet with length > 60 is not allowed", actual_length=len(payload), command=command, command_class=cmd_class)

		header = bytearray(4)
		header[0] = 0
		header[1] = len(payload)
		header[2] = cmd_class
		header[3] = command

		packet = header + bytearray(payload)
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

		events = []

		try:
			while True:
				response_data = self.stream.read_packet(timeout=timeout)
				response = BGAPIPacket(is_event=(response_data[0] == 0x80), command_class=response_data[2], command=response_data[3], payload=response_data[4:])

				if not response.is_event:
					raise InternalError("A BGAPI response was received during a period where only events should have been received", response=response)
				
				events.append(response)
		except TimeoutError:
			pass

		return events

	def scan(self, timeout=4.0):
		"""
		Scan for BLE devices for a fixed period of time
		"""

		# Possible payloads are:
		# 0: only limited discoverable devices
		# 1: generic and limited discoverable devices
		# 2: all devices regardless of discoverability

		response = self._send_command(6, 2, [2])
		if response.payload[0] != 0:
			raise HardwareError("Could not initiate scan for ble devices", error_code=response.payload[0], response=response)

		
		scan_events = self._accumulate_events(timeout)

		response = self._send_command(6, 4, [])
		if response.payload[0] != 0:
			raise HardwareError("Could not stop scanning for ble devices", error_code=response.payload[0], response=response)

		return scan_events