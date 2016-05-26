# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from iotilecore.commander.transport.cmdstream import CMDStream
from iotilecore.commander.commands import RPCCommand
from iotilecore.exceptions import *
from iotilecore.commander.exceptions import *
import hashlib
import json

class RecordedStream (CMDStream):
	def __init__(self, filepath):
		self.filepath = filepath
		self._load_recording()
		
	def _send_rpc(self, address, feature, command, *args, **kwargs):
		rpc = RPCCommand(address, feature, command, *args)

		payload = rpc._format_args()
		payload = payload[:rpc.spec]

		hashval = self._hash_call(address, feature, command, payload)
		if hashval.hexdigest() not in self.recording:
			raise HardwareError("Attempting to make an unknown RPC on a RecordedStream", address=address, feature=feature, command=command, payload=payload)

		status, payload = self.recording[hashval.hexdigest()]
		return status, payload

	def _reset(self):
		pass

	def close(self):
		pass

	def _hash_call(self, addr, feature, command, payload):
		msg = bytearray(chr(addr) + chr(feature) + chr(command) + payload)
		return hashlib.sha256(msg)

	def _load_recording(self):
		self.recording = {}

		with open(self.filepath, "r") as f:
			res = json.load(f)

		for call, resp in res.iteritems():
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

			self.recording[hashval.hexdigest()] = [status, payload]
