# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import os.path
from iotilebuild.mib.descriptor import MIBDescriptor
import unittest
from nose.tools import *
from iotilecore.exceptions import *
import hashlib
import tempfile
import shutil
import atexit

import pyparsing

def _create_tempfolder():
	folder = tempfile.mkdtemp()

	atexit.register(shutil.rmtree, folder)
	return folder

def _load_mib(filename):
	path = os.path.join(os.path.dirname(__file__), filename)
	return MIBDescriptor(path, include_dirs=[os.path.dirname(__file__)])

def test_c_file_generation():
	mib = _load_mib('configvariables.mib')
	block = mib.get_block()

	tmp = _create_tempfolder()

	block.create_c(tmp)

	with open(os.path.join(tmp, 'command_map_c.c'), 'r') as f:
		print f.read()

	with open(os.path.join(tmp, 'command_map_c.h'), 'r') as f:
		print f.read()

	#Make sure the above completes without an exceptions
