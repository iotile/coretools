import os.path
from pymomo.mib.block import MIBBlock
import unittest
from nose.tools import *
from pymomo.exceptions import *
from pymomo.utilities import intelhex

def _load_hex(filename):
	path = os.path.join(os.path.dirname(__file__), 'hex_files', filename)
	ih = intelhex.IntelHex16bit(path)
	return MIBBlock(ih)

def _check_mib_block(block):
	assert block.valid
	assert len(block.interfaces) == 1
	assert len(block.commands) == 1

	cmd1_id = block.commands.keys()[0]
	cmd1 = block.commands[cmd1_id]

	print cmd1
	assert cmd1_id == 12345

def test_valid_12lf1822():
	block = _load_hex('exp_module_12lf1822_app.hex')

	print str(block)
	_check_mib_block(block)

def test_valid_16lf1847():
	block = _load_hex('exp_module_16lf1847_app.hex')

	print str(block)
	_check_mib_block(block)
