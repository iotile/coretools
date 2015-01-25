from pymomo.utilities import typedargs
from pymomo.utilities.typedargs import type_system
import unittest
from nose.tools import *
import os.path
from pymomo.exceptions import *

def test_splitting():
	base, is_complex, subs = type_system.split_type('map(string, integer)')
	assert base == 'map'
	assert is_complex == True
	assert len(subs) == 2
	assert subs[0] == 'string'
	assert subs[1] == 'integer'

def test_map_type():
	mapper = type_system.get_type('map(string, string)')

def test_map_formatting():
	val = {'hello': 5}

	formatted = type_system.format_value(val, 'map(string, integer)')
	assert formatted == 'hello: 5'

def test_list_type():
	mapper = type_system.get_type('list(integer)')

def test_list_formatting():
	val = [10, 15]

	formatted = type_system.format_value(val, 'list(integer)')
	assert formatted == "10\n15"
