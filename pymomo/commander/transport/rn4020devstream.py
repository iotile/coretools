from pymomo.commander.transport.rn4020devboard import RN4020SerialBoard
from pymomo.commander.transport.cmdstream import CMDStream
from pymomo.commander.commands import RPCCommand
from pymomo.exceptions import *
from pymomo.commander.exceptions import *
import atexit 

class RN4020DevStream (CMDStream):
	def __init__(self, port, mac):
		self.port = port
		self.mac = mac
		self.board = RN4020SerialBoard(self.port)
		
		self.board.connect(self.mac)
		atexit.register(self.board.disconnect)

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
