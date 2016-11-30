# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from iotile.core.utilities import typedargs
from iotile.core.utilities.typedargs import type_system
import unittest
import os.path
from iotile.core.exceptions import *

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
