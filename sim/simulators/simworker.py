#simworker.py
#Base class for worker objects that implement PIC simulators
from pymomo.exceptions import *
import time
import select

class SimWorker:
	def __init__(self, pipe):
		self.pipe = pipe
		self._build_sim()

	def _build_sim(self):
		raise APIError("SimWorker subclasses must override _build_sim()")

	def _build_message(self, error=False, message=None, **kwargs):
		msg = {
			'error': error,
			'message': message,
		}

		msg.update(kwargs)
		return msg

	def _format_error(self, message, **kwargs):
		return self._build_message(error=True, message=message, **kwargs)


	def _check_cmd(self, cmd):
		if not isinstance(cmd, dict):
			raise APIError("Command packet is not a dictionary")

		if "method" not in cmd:
			raise APIError("No method specified in command packet")

	def send_error(self, message, **kwargs):
		msg = self._format_error(message, **kwargs)
		self.pipe.send(msg)

	def send_message(self, **kwargs):
		msg = self._build_message(**kwargs)
		self.pipe.send(msg)

	def _dispatch_cmd(self, cmd):
		"""
		Map the command to one of our methods.  Return False if quit
		is invoked
		"""
		method = cmd['method']

		if method == 'quit':
			self.pipe.send(self._build_message(message="Quit command successful"))
			return False

		#If the method exists, call it and return the results
		if hasattr(self, method):
			params = cmd.copy()
			del params['method']

			result = getattr(self, method)(**params)
			if result is not None:
				self.send_message(**result)
			else:
				self.send_message()
		else:
			raise APIError('Method does not exist: %s' % method)

		return True

	def run(self):
		"""
		Run forever in a loop until we receive a quit command.
		"""

		while(True):
			try:
				cmd = self.pipe.recv()
				self._check_cmd(cmd)

				if self._dispatch_cmd(cmd) is False:
					self.finish()
					return
			except MoMoException as e:
				#All errors are propogated as exceptions, catch them and 
				#send an error report.

				msg = self._format_error(e.msg, **e.params)
				self.pipe.send(msg)
			except Exception as ex:
				args = ex.args
				if len(args) == 1:
					args = args[0]

				msg = self._format_error(args)
				self.pipe.send(msg)
			except KeyboardInterrupt as ex:
				self.finish()

	def finish(self):
		"""
		Cleanup all the resources associated with this simulator instance.
		Subclasses should override this behavior
		"""

		pass
