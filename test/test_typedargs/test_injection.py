from pymomo.utilities import typedargs
from pymomo.utilities.typedargs import type_system
import unittest
from nose.tools import *
import os.path
from pymomo.exceptions import *

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

@raises(ArgumentError)
def test_external_package_injection_failure():
	"""
	Test type injection raises error from nonexistant path
	"""

	path = os.path.join(os.path.dirname(__file__), 'extra_type_package_nonexistant')
	type_system.load_external_types(path)
