from simworker import SimWorker
from pymomo.utilities.config import ConfigFile
import subprocess
from pymomo.utilities.typedargs.annotate import *
from pymomo.utilities.typedargs.exceptions import *
from pymomo.utilities.asyncio import AsyncLineBuffer

class SIM30 (SimWorker):
	"""
	A SimWorker object encapsulating the sim30 pic24 simulator from microchip
	"""

	prompt = '\rdsPIC30> '

	def _build_sim(self):
		"""
		Create a subprocess for sim30 and wire up its input and output for us to control
		"""

		settings = ConfigFile('settings')
		sim30path = settings['external_tools/sim30']
		
		self.sim = None
		self.sim = subprocess.Popen([sim30path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		self.input = AsyncLineBuffer(self.sim.stdout, separator=SIM30.prompt, strip=True)
		self.waiting = False #Whether or not we are waiting for a prompt to appear

		self._wait_prompt() #discard return value because its just random information
		self._init_sim()

	def _init_sim(self):
		self._set_mode('pic24')
		self.first_run = True

	def finish(self):
		if self.sim is not None:
			self.sim.terminate()

	def _wait_prompt(self, timeout=3):
		"""
		Wait for a prompt to appear indicating that the last command finished. 
		"""

		#if this returns we know that the end of buffer is SIM30.prompt
		#so we can splice it off
		
		msg = self.input.readline(timeout)
		self.waiting = False

		return msg

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
			result = self._wait_prompt()
			return result
		else:
			return None

	@param("mode", "string", ("list", ['pic24']))
	def _set_mode(self, mode):
		result = self._command('LD %s' % 'pic24super')

	### BEGIN SIMULATION COMMANDS ###
	def load_program(self, program, type):
		#FIXME, look for spaces in program path and raise an
		#error.  sim30 cannot handle spaces in program paths.
		cmd = 'LP'

		if type == 'coff':
			cmd = 'LC'

		result = self._command(cmd, program)
		if len(result) != 0:
			raise InternalError(result)

		#We need to 
		self.first_run = True

	def wait(self, timeout):
		if not self.waiting:
			return

		self._wait_prompt(timeout)

	def set_log(self, file):
		#FIXME, actually attach a log file
		pass

	def execute(self):
		#sim30 requires the processor to be reset before executing
		#code the first time or it dies for an unknown reason.
		if self.first_run:
			self._command('RP')
			self.first_run = False

		self._command('E', sync=False)
		self.waiting = True

		#Nothing should be returned if successful, so a read should timeout
		success = True
		try:
			msg = self._wait_prompt(0.1)
			if msg != "":
				success = False
		except TimeoutError:
			pass

		if success is False:
			raise InternalError(msg)
