#fixtures.py

import pytest
from pymomo.commander.exceptions import *

@pytest.fixture
def controller():
	"""
	Return a controller object attached to the first FTDI adapter plugged into 
	this computer.
	"""

	from pymomo.commander.meta.initialization import get_controller

	try:
		con = get_controller()
	except InitializationException as e:
		pytest.skip("Cannot find FSU to communicate with hardware")

	return con