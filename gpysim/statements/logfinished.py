from logstatement import LogStatement

class LogFinished (LogStatement):
	def __init__(self, statement, log):
		if len(statement['data']) != 0:
			raise ValueError('Invalid finished logging statement, data length != 0 (len=%d)' % len(statement['data']))

		self.address = log.current_address

	def format(self):
		return "Test Exited Successfully"