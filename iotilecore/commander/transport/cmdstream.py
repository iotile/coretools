# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from iotilecore.commander.exceptions import *
from iotilecore.exceptions import *
from iotilecore.commander.commands import RPCCommand
import atexit
import json
import binascii

open_streams = set()

def do_final_close():
	"""
	Make sure that all streams are properly closed at shutdown
	"""

	#Make a copy since stream.close will remove the stream from the master set
	streams = open_streams.copy()
	for stream in streams:
		stream.close()

atexit.register(do_final_close)


class CMDStream (object):
	"""
	Any physical method that supports talking to an IOTile based device

	All interactions with the IOTile device will be via one of the primitive operations defined in this
	class. Specific implementations may transfer the data in their own way and add additional layers 
	as needed. Examples of CMDStream implementations are:
	- the Field Service Unit communicating over a USB <-> Serial bridge
	- Bluetooth LE (directly)
	- Bluetooth LE by way of the RN4020 module connected to a USB port of the com
	"""

	def __init__(self, port, connection_string, record=None):
		self.connection_string = connection_string
		self.connected = False
		self.port = port
		self.record = record
		self.opened = True

		open_streams.add(self)

		if self.record is not None:
			self._recording = {}

		if self.connection_string != None:
			self.connect(self.connection_string)

	def scan(self):
		"""Scan for available IOTile devices

		Scan for connected device and return a map of UUIDs and connection strings for 
		all of the devices that were found.
		"""

		if not hasattr(self, '_scan'):
			raise StreamOperationNotSupportedError(command="scan")

		return self._scan()

	def connect(self, connection_string):
		"""Given a CMDStream subclass specific connection string, connect to a specific device
		"""
		if self.connected:
			raise HardwareError("Cannot connect when we are already connected")

		if not hasattr(self, '_connect'):
			raise StreamOperationNotSupportedError(command="connect")

		self._connect(connection_string)
		self.connected = True
		self.connection_string = connection_string

	def disconnect(self):
		"""Disconnect from the device that we are currently connected to
		"""
		if not self.connected:
			raise HardwareError("Cannot disconnect when we are not connected")

		if not hasattr(self, '_disconnect'):
			raise StreamOperationNotSupportedError(command="disconnect")

		self._disconnect()
		self.connected = False


	def send_rpc(self, address, feature, command, *args, **kwargs):
		if not self.connected:
			raise HardwareError("Cannot send an RPC if we are not in a connected state")

		if not hasattr(self, '_send_rpc'):
			raise StreamOperationNotSupportedError(command="send_rpc")

		status, payload = self._send_rpc(address, feature, command, *args, **kwargs)

		#If we are recording this, save off the call and response
		if self.record is not None:
			rpc = RPCCommand(address, feature, command, *args)
			call_payload = rpc._format_args()
			call_payload = call_payload[:rpc.spec]

			if self.connection_string not in self._recording:
				self._recording[self.connection_string] = []

			call = "{0},{1},{2},{3}".format(address, feature, command, binascii.hexlify(call_payload))
			response = "{0},{1}".format(status, binascii.hexlify(payload))

			self._recording[self.connection_string].append((call, response))

		if status == 0:
			raise ModuleBusyError(address)
		elif status == 0xFF:
			raise ModuleNotFoundError(address)

		return status, bytearray(payload)

	def enable_streaming(self):
		if not self.connected:
			raise HardwareError("Cannot send an RPC if we are not in a connected state")

		if not hasattr(self, '_enable_streaming'):
			raise StreamOperationNotSupportedError(command="enable_streaming")

		return self._enable_streaming()

	def heartbeat(self):
		if not hasattr(self, '_heartbeat'):
			raise StreamOperationNotSupportedError(command="heartbeat")

		return self._heartbeat()

	def reset(self):
		if not hasattr(self, '_reset'):
			raise StreamOperationNotSupportedError(command="reset")

		self._reset()

	def close(self):
		if not self.opened:
			print("close called twice on the same stream")
			return

		try:
			if not hasattr(self, '_close'):
				raise StreamOperationNotSupportedError(command="close")

			self._close()
		finally:
			#Make sure that no matter what happens we save this recording out
			self._save_recording()
			self.opened = False
			open_streams.remove(self)

	def _save_recording(self):
		if not self.record:
			return

		with open(self.record, "w") as f:
			json.dump(self._recording, f, indent=4)

		self.record = False
