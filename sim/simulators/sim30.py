from simworker import SimWorker
from pymomo.utilities.config import ConfigFile
import subprocess
from pymomo.utilities.typedargs.annotate import *
from pymomo.utilities.typedargs.exceptions import *
from pymomo.utilities.asyncio import AsyncLineBuffer
from collections import namedtuple

messages = {
	'CORE-W0008: Software Reset Instruction called at PC=': '_parse_reset'
}

#Types of sim30 messages
SoftwareResetMessage = namedtuple('SoftwareResetMessage', ['pc'])

class SIM30 (SimWorker):
	"""
	A SimWorker object encapsulating the sim30 pic24 simulator from microchip
	"""

	prompt = '\rdsPIC30> '
	known_params = set(['model'])

	def _build_sim(self):
		"""
		Create a subprocess for sim30 and wire up its input and output for us to control
		"""
		
		self.sim = None
		self.sim = subprocess.Popen(['sim30'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		self.input = AsyncLineBuffer(self.sim.stdout, separator=SIM30.prompt, strip=True)
		self.waiting = False #Whether or not we are waiting for a prompt to appear
		self.model = 'pic24super'

		self._wait_prompt(noparse=True) #discard messages because its just random information
		self._init_sim()

	def _init_sim(self):
		self._set_mode(self.model)
		self.first_run = True

	def finish(self):
		if self.sim is not None:
			self.sim.terminate()

	def _wait_prompt(self, timeout=3, noparse=False):
		"""
		Wait for a prompt to appear indicating that the last command finished. 
		"""

		#if this returns we know that the end of buffer is SIM30.prompt
		#so we can splice it off
		
		msg = self.input.readline(timeout)
		self.waiting = False

		if not noparse:
			parsed = self._process_sim30_message(msg)
			return parsed

	def _process_sim30_message(self, msg):
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

	def _command(self, cmd, *args, **kwargs):
		"""
		Send the command cmd to the simulator and wait for a prompt
		to appear again signaling that it has finished executing. if
		additional args are passed, they are converted to strings,
		separated with spaces and appended to cmd, which must be a 
		string.
		"""

		if len(args) > 0:
			argstr = " ".join(args)
			cmd = cmd + " " + argstr

		if cmd[-1] != '\n':
			cmd += '\n'

		self.sim.stdin.write(cmd)

		if "sync" not in kwargs or kwargs["sync"]:
			noparse = kwargs.get('noparse', False)
			result = self._wait_prompt(noparse=noparse)
			return result
		else:
			return None

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

	def wait(self, timeout):
		if not self.waiting:
			return None

		res = self._wait_prompt(timeout)

		return {'result': res}

	def set_log(self, file):
		self._command('io nul %s' % file)

	def ready(self):
		if not self.waiting:
			return {'result': True}

		try:
			self._wait_prompt(0.0)
		except TimeoutError:
			return {'result': False}

		return {'result': True}

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
