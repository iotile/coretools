from pymomo.utilities.typedargs import type_system
from pymomo.utilities import typedargs
from nose.tools import *
from pymomo.exceptions import *

def test_simplereturntype():
	@typedargs.return_type("string")
	def returns_string():
		return "hello"

	val = returns_string()
	formed = type_system.format_return_value(returns_string, val)

	assert formed == "hello"

def test_complexreturntype():
	@typedargs.return_type("map(string, integer)")
	def returns_map():
		return {"hello": 5}

	val = returns_map()
	formed = type_system.format_return_value(returns_map, val)

	assert formed == "hello: 5"
