from simworker import SimWorker
from pymomo.utilities.config import ConfigFile
import subprocess
from pymomo.utilities.typedargs.annotate import *

class SIM30 (SimWorker):
	"""
	A SimWorker object encapsulating the sim30 pic24 simulator from microchip
	"""

	prompt = 'dsPIC30> '

	def _build_sim(self):
		"""
		Create a subprocess for sim30 and wire up its input and output for us to control
		"""

		settings = ConfigFile('settings')
		sim30path = settings['external_tools/sim30']
		
		self.sim = None
		self.sim = subprocess.Popen([sim30path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		self._wait_prompt() #discard return value because its just random information
		self._init_sim()

	def _init_sim(self):
		self._set_mode('pic24')

	def finish(self):
		if self.sim is not None:
			self.sim.terminate()

	def _wait_prompt(self):
		"""
		Wait for a prompt to appear indicating that the last command finished. 
		"""

		#if this returns we know that the end of buffer is SIM30.prompt
		#so we can splice it off
		buffer = self.read_until(self.sim.stdout, SIM30.prompt)
		buffer = buffer[:-len(SIM30.prompt)]
		return buffer

	def _command(self, cmd):
		"""
		Send the command cmd to the simulator and wait for a prompt
		to appear again signaling that it has finished executing.
		"""

		if cmd[-1] != '\n':
			cmd += '\n'

		self.sim.stdin.write(cmd)
		result = self._wait_prompt()
		return result

	@param("mode", "string", ("list", ['pic24']))
	def _set_mode(self, mode):
		result = self._command('LD %s' % 'pic24super')