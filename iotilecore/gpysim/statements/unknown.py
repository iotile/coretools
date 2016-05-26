# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from logstatement import LogStatement

class UnknownStatement (LogStatement):
	def __init__(self, statement, log):
		self.statement = statement
		self.pull_info(log)

	def keep(self):
		return True

	def format(self):
		return "Unknown Logging Statement (type=%d)" % self.statement['control']['value']