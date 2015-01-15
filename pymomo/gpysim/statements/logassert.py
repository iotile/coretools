from logstatement import LogStatement

class LogAssert (LogStatement):
	def __init__(self, statement, log):
		if len(statement['data']) != 2:
			raise ValueError('Invalid assert logging statement, data length != 2 (len=%d)' % len(statement['data']))

		self.actual = statement['data'][0]['value']
		self.desired = statement['data'][1]['value']

		self.address = log.current_address

	def format(self):
		return "ASSERT FAILED (was 0x%X, wanted 0x%X)" % (self.actual, self.desired)

	def error(self):
		return True