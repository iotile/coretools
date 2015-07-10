from pymomo.commander.transport.rn4020devboard import RN4020SerialBoard
from pymomo.commander.transport.cmdstream import CMDStream
from pymomo.commander.commands import RPCCommand
import atexit 

class RN4020DevStream (CMDStream):
	def __init__(self, port, mac):
		self.port = port
		self.mac = mac
		self.board = RN4020SerialBoard(self.port)
		
		self.board.connect(self.mac)
		atexit.register(self.board.disconnect)

	def _send_rpc(self, address, feature, command, *args):
		rpc = RPCCommand(address, feature, command, *args)

		payload = rpc._format_args()
		payload = payload[:rpc.spec]

		response = self.board.send_mib_packet(address, feature, command, payload)
		status = ord(response[0])
		length = ord(response[3])
		
		mib_buffer = response[4:4+length]
		assert len(mib_buffer) == length

		return status, mib_buffer

	def _reset(self):
		self.board.reboot()
		self.board.connect(self.mac)
