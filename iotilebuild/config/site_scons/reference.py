# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#reference.py
#Object to store and retrieve common include directories

import utilities

class Reference:
	def __init__(self):
		conf = utilities.load_settings()

		self.ref = conf['reference']