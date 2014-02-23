#instruction.py

from instructions import *

class Instruction:
	"""
	A representation of a pic 8-bit enhanced midrange instruction
	built from either a string mnemonic or decoded from a binary
	opcode.
	"""

	Mnemonics = {}

	def __init__(self, instruction):
		"""
		Given either a mnemonic string or a binary opcode,
		build the corresponding instruction object.
		"""

		if isinstance(instruction, basestring):
			self._parse_mnemonic(instruction)
		else:
			self._parse_opcode(instruction)

	def _parse_mnemonic(self, instruction):
		instr = instruction.lstrip().rstrip()
		op,sep,args = instr.partition(' ')

		if len(args) != 0: 
			arglist = map(lambda x: x.lstrip().rstrip(), args.split(","))
		else:
			arglist = []

		if op not in Instruction.Mnemonics:
			raise ValueError("Unknown Mnemonic passed to _parse_mnenomic: %s" % op)
		
		self.op = Instruction.Mnemonics[op](arglist)

	def encode(self):
		"""
		Get the binary opcode for this instruction
		"""

		return self.op.encode()


Instruction.Mnemonics['retlw'] = RetlwInstruction
Instruction.Mnemonics['goto'] = GotoInstruction