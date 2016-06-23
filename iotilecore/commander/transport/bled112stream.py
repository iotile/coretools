# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from iotilecore.commander.transport.bled112dongle import BLED112Dongle
from iotilecore.commander.transport.cmdstream import CMDStream
from iotilecore.commander.commands import RPCCommand
from iotilecore.exceptions import *
from iotilecore.commander.exceptions import *
import atexit 

class BLED112Stream (CMDStream):
	def __init__(self, port, mac):
		self.port = port
		self.mac = mac
		self.dongle = BLED112Dongle(self.port)
		
		self.conn = self.dongle.connect(self.mac, timeout=6.0)
		self.boardopen = True

		self.services = self.dongle.probe_device(self.conn)

		#Check and see if we're using a new style btle protocol or the old mldp based one
		if self.dongle.TileBusService in self.services:
			self.protocol = "tilebus"
			self.dongle.set_notification(self.conn, self.services[self.dongle.TileBusService]['characteristics'][self.dongle.TileBusReceiveHeaderCharacteristic], True)
			self.dongle.set_notification(self.conn, self.services[self.dongle.TileBusService]['characteristics'][self.dongle.TileBusReceivePayloadCharacteristic], True)
		else:
			self.protocol = "mldp"
			self.dongle.start_mldp(self.conn, self.services, version="v1")
		
		atexit.register(self.close)

	def _send_rpc(self, address, feature, command, *args, **kwargs):
		rpc = RPCCommand(address, feature, command, *args)

		payload = rpc._format_args()
		payload = payload[:rpc.spec]

		try:
			if self.protocol == "mldp":
				response = self.dongle.send_mib_packet(self.conn, self.services, address, feature, command, payload, **kwargs)
			else:
				response = self.dongle.send_tilebus_packet(self.conn, self.services, address, feature, command, payload, **kwargs)
			
			status = ord(response[0])

			#Only read the length of the packet if the has data bit is set
			#If no one responds, the length is 0 as well
			if status == 0xFF and ord(response[1]) == 0xFF:
				length = 0
			elif (status & 1 << 7):
				length = ord(response[3])
			else:
				length = 0
		
			mib_buffer = response[4:4+length]
			assert len(mib_buffer) == length

			return status, mib_buffer
		except TimeoutError:
			if address == 8:
				raise ModuleNotFoundError(address)
			else:
				raise HardwareError("Timeout waiting for a response from the remote BTLE module", address=address, feature=feature, command=command)

	def _enable_streaming(self):
		if self.protocol == 'tilebus':
			self.dongle.set_notification(self.conn, self.services[self.dongle.TileBusService]['characteristics'][self.dongle.TileBusStreamingCharacteristic], True)
			self.dongle.stream_enabled = True

			return self.dongle._get_streaming_queue()
		else:
			raise HardwareError("Transport protocol does not support streaming")

	def _reset(self):
		self.board.reboot()
		self.board.connect(self.mac)

	def close(self):
		if self.boardopen:
			self.dongle.disconnect(self.conn)
			self.dongle.io.close()
			self.boardopen = False
