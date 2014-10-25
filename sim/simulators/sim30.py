from externalsim import ExternalSimulator
from pymomo.utilities.config import ConfigFile
import subprocess
from pymomo.utilities.typedargs.annotate import *
from pymomo.exceptions import *
from pymomo.utilities.asyncio import AsyncLineBuffer
from collections import namedtuple

messages = {
	'CORE-W0008: Software Reset Instruction called at PC=': '_parse_reset'
}

#Types of sim30 messages
SoftwareResetMessage = namedtuple('SoftwareResetMessage', ['pc'])

class SIM30 (ExternalSimulator):
	"""
	An ExternalSimulator object encapsulating the sim30 pic24 simulator from microchip
	"""

	prompt = '\rdsPIC30> '
	known_params = set(['model'])

	def _sim_path(self):
		return ['sim30']

	def _initialize(self):
		self.model = 'pic24super'
		self._init_sim()

	def _init_sim(self):
		self._set_mode(self.model)
		self.first_run = True

	def _process_message(self, msg, cmd=None):
		"""
		Given the textual output of a sim30 response to a command, parse it and
		see if it indicates an error.  Convert the result to a standard format
		for further inspection as well.
		"""

		msg = msg.rstrip()
		lines = [x for x in msg.split('\n') if len(x) > 0]

		parsed = []

		for line in lines:
			matches = [messages[x] for x in messages.iterkeys() if line.startswith(x)]
			if len(matches) == 0:
				raise APIError("Unknown message from sim30: %s" % line)
			elif len(matches) > 1:
				raise APIError("Multiple matches for message from sim30: %s" % line)

			parser = getattr(self, matches[0])
			parsed.append(parser(line))
		
		return parsed

	def _set_mode(self, mode):
		result = self._command('LD %s' % mode, noparse=True)

	### BEGIN SIMULATION COMMANDS ###
	def load_program(self, program, type):
		#FIXME, look for spaces in program path and raise an
		#error.  sim30 cannot handle spaces in program paths.
		cmd = 'LP'

		if type == 'coff' or type== 'elf':
			cmd = 'LC'

		result = self._command(cmd, program)
		if len(result) != 0:
			raise InternalError(result)

		#We need to 
		self.first_run = True

	def set_param(self, name, value):
		if name in self.known_params:
			setattr(self, name, value)

		if name == 'model':
			self._init_sim()

	def set_log(self, file):
		self._command('io nul %s' % file)

	def execute(self):
		#sim30 requires the processor to be reset before executing
		#code the first time or it dies for an unknown reason.
		if self.first_run:
			self._command('RP')
			self.first_run = False

		#Stop execution on each warning so that we can regain control after a 
		#reset instruction.
		self._command('HW on')
		self._command('E', sync=False)
		self.waiting = True


	#Utility routines for parsing specific messages from sim30
	def _parse_reset(self, line):
		skip = len('CORE-W0008: Software Reset Instruction called at PC=')
		pcstr = line[skip:]
		pc = int(pcstr, 16)

		msg = SoftwareResetMessage(pc)
		return msg
