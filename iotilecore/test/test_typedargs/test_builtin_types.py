# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import pytest
from iotile.core.utilities.typedargs import type_system
from iotile.core.utilities import typedargs
from iotile.core.exceptions import *

def test_builtins_exist():
	builtin = ['integer', 'path', 'string']

	for b in builtin:
		type_system.get_type(b)

def test_builtin_conversions():
	val = type_system.convert_to_type('42', 'integer')
	assert val == 42

	val = type_system.convert_to_type('/users/timburke', 'path')
	assert val == '/users/timburke'

	val = type_system.convert_to_type('hello', 'string')
	assert val == 'hello'

def test_annotation_correct():
	@typedargs.param("string_param", "string", desc='Hello')
	def function_test(string_param):
		pass

	function_test("hello")

def test_annotation_unknown_type():
	with pytest.raises(ArgumentError):
		@typedargs.param("string_param", "unknown_type", desc='Hello')
		def function_test(string_param):
			pass

		function_test("hello")

def test_annotation_validation():
	with pytest.raises(ValidationError):
		@typedargs.param("int_param", "integer", "nonnegative", desc="No desc")
		def function_test(int_param):
			pass

		function_test(-1)

def test_bool_valid():
	val = type_system.convert_to_type('True', 'bool')
	assert val == True

	val = type_system.convert_to_type('false', 'bool')
	assert val == False

	val = type_system.convert_to_type(True, 'bool')
	assert val == True

	val = type_system.convert_to_type(False, 'bool')
	assert val == False

	val = type_system.convert_to_type(None, 'bool')
	assert val is None

	val = type_system.convert_to_type(0, 'bool')
	assert val == False
	
	val = type_system.convert_to_type(1, 'bool')
	assert val == True

def test_format_bool():
	val = type_system.format_value(True, 'bool')
	assert val == 'True'

	val = type_system.format_value(False, 'bool')
	assert val == 'False'
