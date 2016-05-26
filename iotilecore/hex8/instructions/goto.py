# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from utils import *

class GotoInstruction:
	def __init__(self, args):
		self.args = parse_args("a", args)

	def __str__(self):
		return "goto 0x%x" % self.args[0]

	def encode(self):
		return (0b101 << 11) | self.args[0]