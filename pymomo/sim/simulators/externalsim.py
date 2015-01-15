#externalsim.py
#A SimWorker that encapsulates an external program where commands are
#fed in using stdin and results are collected using stdout

from simworker import SimWorker
import subprocess
from pymomo.utilities.typedargs.annotate import *
from pymomo.exceptions import *
from pymomo.utilities.asyncio import AsyncLineBuffer

class ExternalSimulator (SimWorker):
	"""
	A SimWorker that encapsulates an external simulator program, sending
	commands to stdin and reading results from stdout.  This class provides
	many convenience routines for interacting with the program in reliable ways.
	"""

	def _sim_path(self):
		"""
		Subclasses override to return an array with the
		path and arguments to be used to create a subprocess
		for this simulator
		"""

		raise APIError("ExternalSimulator subclasses must override _sim_path() or _build_sim()")

	def _initialize(self):
		"""
		Subclasses can override in order to perform specific simulator
		initialization routines here.  This is called from _build_sim
		"""

		pass

	def _process_message(self, msg, cmd=None):
		"""
		Subclasses can override in order to process the messages that are returned from the
		simulator after executing a command.
		"""

		return msg

	def _build_sim(self):
		"""
		Create a subprocess for the external simulator and wire up its input and output for us to control
		"""
		

		simargs = self._sim_path()

		if not hasattr(self, 'prompt'):
			raise APIError("Subclasses of ExternalSimulator must define an attribute called prompt")

		self.sim = None
		self.sim = subprocess.Popen(simargs, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		self.input = AsyncLineBuffer(self.sim.stdout, separator=self.prompt, strip=True)
		self.waiting = False #Whether or not we are waiting for a prompt to appear
		self.waiting_cmd = None

		self._wait_prompt(noparse=True) #discard messages because its just random information
		self._initialize()

	def finish(self):
		if self.sim is not None:
			self.sim.terminate()

	def ready(self):
		if not self.waiting:
			return {'result': True}

		try:
			self._wait_prompt(0.0, cmd=self.waiting_cmd)
		except TimeoutError:
			return {'result': False}

		return {'result': True}

	def wait(self, timeout):
		if not self.waiting:
			return None

		res = self._wait_prompt(timeout)

		return {'result': res}

	def _wait_prompt(self, timeout=3, noparse=False, cmd=None):
		"""
		Wait for a prompt to appear indicating that the last command finished. 
		"""

		#if this returns we know that the end of buffer is self.prompt
		#so we can splice it off
		
		msg = self.input.readline(timeout)
		self.waiting = False

		if not noparse:
			parsed = self._process_message(msg, cmd=cmd)
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
			result = self._wait_prompt(noparse=noparse, cmd=cmd)
			return result
		else:
			self.waiting_cmd = cmd
			return None
