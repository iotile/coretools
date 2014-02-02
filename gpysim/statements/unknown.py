from logstatement import LogStatement

class UnknownStatement (LogStatement):
	def __init__(self, statement, log):
		self.statement = statement
		self.pull_info(log)

	def keep(self):
		return True

	def format(self):
		return "Unknown Logging Statement (type=%d)" % self.statement['control']['value']