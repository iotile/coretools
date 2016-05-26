# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#fixtures.py

import pytest
from iotilecore.commander.exceptions import *

@pytest.fixture
def controller():
	"""
	Return a controller object attached to the first FTDI adapter plugged into 
	this computer.
	"""

	from iotilecore.commander.meta.initialization import get_controller

	try:
		con = get_controller()
	except InitializationException as e:
		pytest.skip("Cannot find FSU to communicate with hardware")

	return con