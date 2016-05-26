# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from logstatement import LogStatement

class LogFinished (LogStatement):
	def __init__(self, statement, log):
		if len(statement['data']) != 0:
			raise ValueError('Invalid finished logging statement, data length != 0 (len=%d)' % len(statement['data']))

		self.address = log.current_address

	def format(self):
		return "Test Exited Successfully"