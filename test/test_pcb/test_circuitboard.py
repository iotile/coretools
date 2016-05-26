# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import unittest
import os.path
import os
from nose.tools import *
from iotilecore.exceptions import *
from iotilecore.pcb import CircuitBoard
import tempfile
import shutil

def test_check_attributes():
	#Board is missing Company and Dimension unit attributes
	board = os.path.join(os.path.dirname(__file__), 'eagle', 'controller_missing_attrs.brd')
	b = CircuitBoard(board)

	assert b.is_clean() == False
	errors = b.get_errors()
	warnings = b.get_warnings()

	print errors
	print warnings

	assert len(errors) == 3
	assert len(warnings) == 0
