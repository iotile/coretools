# simulator.py
# Generic interface for controlling PIC microchip simulators
#
# Designed to work with sim30 from Microchip for simulating PIC24
# chips and gpsim to simulate pic12 and pic16 chips.

import simulators
from pymomo.utilities.typedargs.annotate import *
from pymomo.utilities.typedargs.exceptions import *
from multiprocessing import Process, Queue, Pipe
import atexit

def _spawn_simulator(sim_type, child_pipe):
	"""
	Spawn a simulator of the given type, attaching child_pipe to it
	so that we can communicate with it.
	"""

	sim = sim_type(child_pipe)
	sim.run()

def _quit_simulator(sim):
	"""
	Quit the simulator process.
	"""
	sim.quit()


class Simulator:
	"""
	Generic interface for simulating embedded microprocessors.
	Subclasses should implement specific methods as a worker
	object that is spawned in a separate process.
	"""

	@param("type", "string", desc="Type of simulator to create (pic24 or pic12)")
	def __init__(self, type):
		"""
		Create a simulator object in a separate process 
		"""

		if not hasattr(simulators, type):
			raise ValueError("Unknown simulator type passed: %s" % str(type))

		self.sim_type = getattr(simulators, type)
		self._pipe, child_pipe = Pipe(duplex=True)

		self.process = Process(target=_spawn_simulator, args=(self.sim_type, child_pipe))
		self.process.start()

		#Make sure we always quit the simulator when we exit so that we don't hang
		atexit.register(_quit_simulator, self)

	@annotated
	def quit(self):
		"""
		Tell the simulator to quit and wait for it to exit.
		"""

		if self.process.is_alive():
			self._command("quit")
			self.process.join()

	@param("program", "path", "readable", desc="Path to program object file to load")
	def load(self, program):
		"""
		Load the program object file into the simulator
		"""

		self._command('load_program', program=program)

	#Communication functions to communicate with the simulator worker objects
	def _send_cmd(self, method, **kwargs):
		msg = {'method': method}
		msg.update(kwargs)

		self._pipe.send(msg)

	def _receive_response(self, timeout=3):
		if not self._pipe.poll(timeout):
			self.process.terminate()
			raise TimeoutError("Waiting for a response from child simulator process.")

		response = self._pipe.recv()
		return response

	def _command(self, method, **kwargs):
		self._send_cmd(method, **kwargs)
		resp = self._receive_response()

		if resp['error'] is True:
			raise APIError("Result of calling method '%s' was '%s'" % (method, resp['message']))

		return resp