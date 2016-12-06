# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import unittest
import os.path
import subprocess
from iotile.core.dev.registry import ComponentRegistry
from iotile.build.build.build import build

def test_iotiletool():
	err = subprocess.check_call(["iotile" , "quit"])
	assert err == 0

def test_build_command():
	"""
	Make sure iotile.build has been properly registered as a plugin
	"""

	reg = ComponentRegistry()

	plugs = reg.list_plugins()
	
	assert 'build' in plugs

def test_iotiletool_build():
	olddir = os.getcwd()

	builddir = os.path.join(os.path.dirname(__file__), 'blank_component')

	try:
		os.chdir(builddir)
		err = subprocess.check_call(["iotile", "build"])
		assert err == 0
	finally:
		os.chdir(olddir)
