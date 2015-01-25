import unittest
import os.path
import os
from nose.tools import *
from pymomo.exceptions import *
from pymomo.pcb import CircuitBoard
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
