from logstatement import LogStatement

class LogHex (LogStatement):
	def __init__(self, statement, log):
		if len(statement['data']) != 1:
			raise ValueError('Invalid hex logging statement, too much data (len=%d)' % len(statement['data']))

		self.data = statement['data'][0]['value']
		self.pull_info(log)

	def format(self):
		return "Logged 0x%X" % (self.data)