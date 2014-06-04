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
import os.path

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
			raise ValidationError("Unknown simulator type passed: %s" % str(type))

		self.sim_type = getattr(simulators, type)
		self._pipe, child_pipe = Pipe(duplex=True)

		self.process = Process(target=_spawn_simulator, args=(self.sim_type, child_pipe))
		self.process.start()

		#Make sure we always quit the simulator when we exit so that we don't hang the
		#executing proces
		atexit.register(_quit_simulator, self)

	@annotated
	def quit(self):
		"""
		Tell the simulator to quit and wait for it to exit
		"""

		if self.process.is_alive():
			self._command("quit")
			self.process.join()

	@param("program", "path", "readable", desc="Path of program object file to load")
	def load(self, program):
		"""
		Load the program object file into the simulator
		"""

		# Try to determine file type
		type = 'unknown'
		ext = os.path.splitext(program)[1]
		if ext == '.coff' or ext == '.cof':
			type = 'coff'
		elif ext == '.elf':
			type = 'elf'
		elif ext == '.hex':
			type = 'hex'

		self._command('load_program', program=program, type=type)

	@param("file", "path", "writeable", desc="Path of log file to generate")
	def set_log(self, file):
		"""
		Upon completion of this simulation, generate a log file containing
		the output of the simulated code at path file.  The log file is not
		guaranteed to be generated until shutdown() is called on the simulator.
		"""

		self._command('set_log', file=file)

	@annotated
	def wait(self):
		"""
		Wait for the simulator to finish executing code and return to being able
		to process commands.
		"""

		self._command('wait')

	@annotated
	def execute(self):
		"""
		Begin or continue program execution
		"""

		self._command('execute')


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
			raise InternalError("Result of calling method '%s' was '%s'" % (method, resp['message']))

		return resp