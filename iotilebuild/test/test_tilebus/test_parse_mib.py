# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import os.path
import pytest
from iotile.build.tilebus.descriptor import TBDescriptor
import unittest
from iotile.core.exceptions import *
import hashlib
import tempfile
import shutil
import atexit

import pyparsing

def _create_tempfile(src=None):
	"""
	Create a named temporary file that is a copy of the src file
	and register for it to be deleted at program exit.
	"""
	dst = tempfile.NamedTemporaryFile(delete=False)

	if src is not None:
		with open(src, "r+b") as f:
			shutil.copyfileobj(f, dst)

	dst.close()

	atexit.register(os.remove, dst.name)
	return dst.name

def _load_mib(filename):
	path = os.path.join(os.path.dirname(__file__), filename)
	tb = TBDescriptor(path, include_dirs=[os.path.dirname(__file__)])
	tb._validate_information()
	return tb

def test_syntax_error():
	with pytest.raises(pyparsing.ParseException):
		_load_mib("syntax_error.mib")

def test_incomplete():
	with pytest.raises(DataError):
		desc = _load_mib("incomplete.mib")

def test_complete():
	desc = _load_mib("complete.mib")

	api = desc.variables['APIVersion']
	mod = desc.variables['ModuleVersion']

	assert api[0] == 1
	assert api[1] == 2

	assert mod[0] == 1
	assert mod[1] == 2
	assert mod[2] == 3

	assert len(desc.variables['ModuleName']) == 6
	assert desc.variables['ModuleName'] == 'test12'

def test_extend_name():
	desc = _load_mib("short_name.mib")

	assert len(desc.variables['ModuleName']) == 6
	assert desc.variables['ModuleName'] == 'test  '

def test_hexvalues():
	desc = _load_mib("hexvalues.mib")

	assert desc.variables['RandomVariable'] == 0x100
	assert 0x12ab in desc.commands
	assert 64000 in desc.commands

def test_parse_configs():
	desc = _load_mib("configvariables.mib")

	assert 0x12ba in desc.configs
	assert 0xabcd in desc.configs
	assert 0x1235 in desc.configs
	assert 0x1236 in desc.configs
	assert 0x5234 in desc.configs

	testvar1 = desc.configs[0x12ba]
	assert testvar1['required'] == True
	assert testvar1['type'] == 'uint8_t'
	assert testvar1['total_size'] == 1
	assert testvar1['name'] == 'testvar1'

def test_config_defaults():
	desc = _load_mib("configvariables.mib")
	testvar4 = desc.configs[0x1236]

	assert testvar4['required'] == False
	assert testvar4['type'] == 'char'
	assert testvar4['total_size'] == 15 

	print len(testvar4['default_value'])
	print len("test string")
	print testvar4['default_value']
	assert len(testvar4['default_value']) == (len("test string") + 2) #Include the quotes
	

def test_value_convesion():
	desc = _load_mib("configvariables.mib")

	buf1 = desc._convert_value_to_bytes(0x10ab, 'uint16_t')
	assert buf1[0] == 0xab
	assert buf1[1] == 0x10

	buf2 = desc._convert_value_to_bytes('hello world', 'char')
	known_val = [ord(x) for x in 'hello world']

	assert len(buf2) == len(known_val)
	for i in xrange(0, len(buf2)):
		assert buf2[i] == known_val[i]

	buf3 = desc._convert_value_to_bytes([0xab12, 0xbcde, 0x1234], 'uint16_t')
	known_val = [0x12, 0xab, 0xde, 0xbc, 0x34, 0x12]

	assert len(buf3) == len(known_val)
	for i in xrange(0, len(buf3)):
		assert buf3[i] == known_val[i]

def test_parse_badconfig1():
	with pytest.raises(pyparsing.ParseException):
		desc = _load_mib("badconfig1.mib")

def test_parse_badconfig2():
	with pytest.raises(pyparsing.ParseException):
		desc = _load_mib("badconfig2.mib")

def test_long_name():
	with pytest.raises(DataError):
		desc = _load_mib("long_name.mib")

def test_include_nonexistent():
	with pytest.raises(pyparsing.ParseException):
		desc = _load_mib("invalid_include.mib")

def test_good_include():
	desc = _load_mib("valid_include.mib")

	api = desc.variables['APIVersion']
	mod = desc.variables['ModuleVersion']

	assert api[0] == 1
	assert api[1] == 2

	assert mod[0] == 1
	assert mod[1] == 2
	assert mod[2] == 3

	assert len(desc.variables['ModuleName']) == 6
	assert desc.variables['ModuleName'] == 'test12'

def test_block_generation():
	desc = _load_mib("complete.mib")

	block = desc.get_block()

	assert block.api_version[0] == 1
	assert block.api_version[1] == 2

	assert block.module_version[0] == 1
	assert block.module_version[1] == 2
	assert block.module_version[2] == 3

	assert len(block.name) == 6
	assert block.name == 'test12'

	str_rep = str(block)
	print str_rep
