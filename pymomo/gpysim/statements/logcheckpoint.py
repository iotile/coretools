from logstatement import LogStatement

class LogCheckpoint (LogStatement):
	def __init__(self, statement, log):
		if len(statement['data']) != 1:
			raise ValueError('Invalid checkpoint logging statement, too much data (len=%d)' % len(statement['data']))

		self.data = statement['data'][0]['value']
		self.pull_info(log)

	def format(self):
		return "Checkpoint passed (logged value: 0x%X)" % self.data