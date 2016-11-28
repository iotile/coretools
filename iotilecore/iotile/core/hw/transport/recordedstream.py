# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from iotile.core.hw.transport.cmdstream import CMDStream
from iotile.core.hw.commands import RPCCommand
from iotile.core.exceptions import *
from iotile.core.hw.exceptions import *
import hashlib
import json

class RecordedStream (CMDStream):
	def __init__(self, filepath, conn_string, record=None):
		self.filepath = filepath
		self.recording = {}
		self.calls = {}

		if record is not None:
			raise ValidationError("You cannot record a session based on an already recorded stream")

		if self.filepath is not None:
			self._load_recording()

		super(RecordedStream, self).__init__(filepath, conn_string)

	def _connect(self, conn_string):
		if conn_string not in self.recording:
			raise HardwareError("Attempting to connect to an unrecorded device in a RecordedStream", connection_string=conn_string, recorded_devices=self.recording.keys())
		
	def _send_rpc(self, address, feature, command, *args, **kwargs):
		rpc = RPCCommand(address, feature, command, *args)

		payload = rpc._format_args()
		payload = payload[:rpc.spec]

		hashval = self._hash_call(address, feature, command, payload)
		if hashval.hexdigest() not in self.recording[self.connection_string]:
			raise HardwareError("Attempting to make a nonrecorded RPC on a RecordedStream", address=address, feature=feature, command=command, payload=payload)

		#Figure out how many calls we've made to this rpc, then retrieve the response to the ith call and update our call counter
		if self.connection_string not in self.calls:
			self.calls[self.connection_string] = {}

		if hashval.hexdigest() not in self.calls[self.connection_string]:
			self.calls[self.connection_string][hashval.hexdigest()] = 0

		call_count = self.calls[self.connection_string][hashval.hexdigest()]

		if call_count >= len(self.recording[self.connection_string][hashval.hexdigest()]):
			raise HardwareError("Attempted to call a recorded RPC more times than were recorded", recorded_calls=len(self.recording[self.connection_string][hashval.hexdigest()]))

		status, payload = self.recording[self.connection_string][hashval.hexdigest()][call_count]

		self.calls[self.connection_string][hashval.hexdigest()] += 1

		return status, payload

	def _reset(self):
		pass

	def _close(self):
		pass

	def _hash_call(self, addr, feature, command, payload):
		msg = bytearray(chr(addr) + chr(feature) + chr(command) + payload)
		return hashlib.sha256(msg)

	def _load_recording(self):
		with open(self.filepath, "r") as f:
			data = json.load(f)

		for dev in data.iterkeys():
			res = data[dev]
			self.recording[dev] = {}

			for call, resp in res:
				addr, feature, command, payload = call.split(",")

				payload = bytearray.fromhex(payload)
				addr = int(addr, 0)
				feature = int(feature, 0)
				command = int(command, 0)

				assert addr >= 0 and addr <= 255
				assert feature >= 0 and feature <= 255
				assert command >= 0 and command <= 255

				hashval = self._hash_call(addr, feature, command, payload)

				#Process response, which is in the format hex status, hex payload
				status, payload = resp.split(",")

				status = int(status, 0)
				payload = bytearray.fromhex(payload)

				#Make sure HasData bit is always set whenever there is actually data
				if len(payload) != 0:
					status |= (1 << 7)

				#Allow multiple calls to the same function returning different things each time

				if hashval.hexdigest() not in self.recording[dev]:
					self.recording[dev][hashval.hexdigest()] = []

				self.recording[dev][hashval.hexdigest()].append((status, payload))
