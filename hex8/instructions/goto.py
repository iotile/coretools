from utils import *

class GotoInstruction:
	def __init__(self, args):
		self.args = parse_args("a", args)

	def __str__(self):
		return "goto 0x%x" % self.args[0]

	def encode(self):
		return (0b101 << 11) | self.args[0]