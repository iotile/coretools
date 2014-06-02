#simworker.py
#Base class for worker objects that implement PIC simulators

class SimWorker:
	def __init__(self, pipe):
		self.pipe = pipe
		self._build_sim()

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
			raise ValueError("Command packet is not a dictionary")

		if "method" not in cmd:
			raise ValueError("No method specified in command packet")

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
			result = self.getattr(method)(cmd['args'])
			msg = self._build_message(**result)
			self.pipe.send(msg)
		else:
			msg = self._format_error('Method does not exist: %s' % method)
			self.pipe.send(msg)

		return True

	def run(self):
		"""
		Run forever in a loop until we receive a quit command.
		"""

		try:
			while(True):
				cmd = self.pipe.recv()
				self._check_cmd(cmd)

				if self._dispatch_cmd(cmd) is False:
					self.finish()
					return
		except ValueError as e:
			#All errors are propogated as exceptions, catch them and 
			#send an error report.
			msg = self._format_error(e.args)
			self.pipe.send(msg)

	def finish(self):
		"""
		Cleanup all the resources associated with this simulator instance.
		Subclasses should override this behavior
		"""

		pass

	def read_until(self, file, match):
		"""
		Read from file until match occurs:
		"""

		if len(match) == 0:
			return

		buffer = bytearray()

		i = 0

		while i<len(match):
			c = file.read(1)
			if c == match[i]:
				i += 1
			else:
				i = 0

			buffer.append(c)

		return str(buffer)
