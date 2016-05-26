# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from logstatement import LogStatement

class LogHex (LogStatement):
	def __init__(self, statement, log):
		if len(statement['data']) != 1:
			raise ValueError('Invalid hex logging statement, too much data (len=%d)' % len(statement['data']))

		self.data = statement['data'][0]['value']
		self.pull_info(log)

	def format(self):
		return "Logged 0x%X" % (self.data)