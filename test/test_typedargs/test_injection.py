from pymomo.utilities import typedargs
import unittest
from nose.tools import *
import os.path
from pymomo.exceptions import *

def test_type_injection():
	typeobj = {}

	assert not typedargs.is_known_type("test_injected_type1")

	typedargs.inject_type("test_injected_type1", typeobj)
	assert typedargs.is_known_type("test_injected_type1")

def test_external_module_injection():
	"""
	Test type injection from an external python module
	"""

	path = os.path.join(os.path.dirname(__file__), 'extra_types')

	assert not typedargs.is_known_type('new_type')
	typedargs.load_external_types(path)
	assert typedargs.is_known_type('new_type')

def test_external_package_injection():
	"""
	Test type injection from an external python package
	"""

	path = os.path.join(os.path.dirname(__file__), 'extra_type_package')

	assert not typedargs.is_known_type('new_pkg_type')
	typedargs.load_external_types(path)
	assert typedargs.is_known_type('new_pkg_type')

@raises(ArgumentError)
def test_external_package_injection_failure():
	"""
	Test type injection raises error from nonexistant path
	"""

	path = os.path.join(os.path.dirname(__file__), 'extra_type_package_nonexistant')
	typedargs.load_external_types(path)
