# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import os.path
from iotile.build.tilebus.descriptor import TBDescriptor
import tempfile
import shutil
import atexit


def _create_tempfolder():
    folder = tempfile.mkdtemp()

    atexit.register(shutil.rmtree, folder)
    return folder

def _load_mib(filename):
    path = os.path.join(os.path.dirname(__file__), filename)
    return TBDescriptor(path, include_dirs=[os.path.dirname(__file__)])

def test_c_file_generation():
    mib = _load_mib('configvariables.mib')
    block = mib.get_block()

    tmp = _create_tempfolder()

    block.create_c(tmp)

    with open(os.path.join(tmp, 'command_map_c.c'), 'r') as f:
        print f.read()

    with open(os.path.join(tmp, 'command_map_c.h'), 'r') as f:
        print f.read()
