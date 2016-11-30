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
import pytest
import os.path
from iotile.core.exceptions import *

def test_type_injection():
	import extra_type_package.extra_type as typeobj

	assert not type_system.is_known_type("test_injected_type1")

	type_system.inject_type("test_injected_type1", typeobj)
	assert type_system.is_known_type("test_injected_type1")

def test_external_module_injection():
	"""
	Test type injection from an external python module
	"""

	path = os.path.join(os.path.dirname(__file__), 'extra_types')

	assert not type_system.is_known_type('new_type')
	type_system.load_external_types(path)
	assert type_system.is_known_type('new_type')

def test_external_package_injection():
	"""
	Test type injection from an external python package
	"""

	path = os.path.join(os.path.dirname(__file__), 'extra_type_package')

	assert not type_system.is_known_type('new_pkg_type')
	type_system.load_external_types(path)
	assert type_system.is_known_type('new_pkg_type')

def test_external_package_injection_failure():
	"""
	Test type injection raises error from nonexistant path
	"""

	with pytest.raises(ArgumentError):
		path = os.path.join(os.path.dirname(__file__), 'extra_type_package_nonexistant')
		type_system.load_external_types(path)
