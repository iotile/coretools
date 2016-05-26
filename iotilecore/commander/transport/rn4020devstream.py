# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from iotilecore.commander.transport.rn4020devboard import RN4020SerialBoard
from iotilecore.commander.transport.cmdstream import CMDStream
from iotilecore.commander.commands import RPCCommand
from iotilecore.exceptions import *
from iotilecore.commander.exceptions import *
import atexit 

class RN4020DevStream (CMDStream):
	def __init__(self, port, mac):
		self.port = port
		self.mac = mac
		self.board = RN4020SerialBoard(self.port)
		
		self.board.connect(self.mac)
		self.boardopen = True
		atexit.register(self.close)

	def _send_rpc(self, address, feature, command, *args, **kwargs):
		rpc = RPCCommand(address, feature, command, *args)

		payload = rpc._format_args()
		payload = payload[:rpc.spec]

		try:
			response = self.board.send_mib_packet(address, feature, command, payload, **kwargs)
			status = ord(response[0])

			#Only read the length of the packet if the has data bit is set
			if (status & 1 << 7):
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

	def _reset(self):
		self.board.reboot()
		self.board.connect(self.mac)

	def close(self):
		if self.boardopen:
			self.board.disconnect()
			self.board.io.close()
			self.boardopen = False
