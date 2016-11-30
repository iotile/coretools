# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from iotile.core.utilities.typedargs import type_system
from iotile.core.utilities import typedargs
from iotile.core.exceptions import *

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
