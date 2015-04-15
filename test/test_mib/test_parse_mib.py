import os.path
from pymomo.mib.descriptor import MIBDescriptor
import unittest
from nose.tools import *
from pymomo.exceptions import *

import pyparsing

def _load_mib(filename):
	path = os.path.join(os.path.dirname(__file__), filename)
	return MIBDescriptor(path)

@raises(pyparsing.ParseException)
def test_syntax_error():
	_load_mib("syntax_error.mib")

@raises(DataError)
def test_incomplete():
	desc = _load_mib("incomplete.mib")

def test_complete():
	desc = _load_mib("complete.mib")