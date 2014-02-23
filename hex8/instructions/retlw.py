from utils import *

class RetlwInstruction:
	def __init__(self, args):
		self.args = parse_args("i", args)

	def __str__(self):
		return "retlw 0x%x" % self.args[0]

	def encode(self):
		return (0b110100 << 8) | self.args[0]