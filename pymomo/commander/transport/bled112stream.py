from pymomo.commander.transport.bled112dongle import BLED112Dongle
from pymomo.commander.transport.cmdstream import CMDStream
from pymomo.commander.commands import RPCCommand
from pymomo.exceptions import *
from pymomo.commander.exceptions import *
import atexit 

class BLED112Stream (CMDStream):
	def __init__(self, port, mac):
		self.port = port
		self.mac = mac
		self.dongle = BLED112Dongle(self.port)
		
		self.conn = self.dongle.connect(self.mac)
		self.services = self.dongle.probe_device(self.conn)

		self.dongle.start_mldp(self.conn, self.services, version="v1")

		self.boardopen = True
		atexit.register(self.close)

	def _send_rpc(self, address, feature, command, *args, **kwargs):
		rpc = RPCCommand(address, feature, command, *args)

		payload = rpc._format_args()
		payload = payload[:rpc.spec]

		try:
			response = self.dongle.send_mib_packet(self.conn, self.services, address, feature, command, payload, **kwargs)
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

	def _reset(self):
		self.board.reboot()
		self.board.connect(self.mac)

	def close(self):
		if self.boardopen:
			self.dongle.disconnect(self.conn)
			self.dongle.io.close()
			self.boardopen = False
