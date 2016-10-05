# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import SCons.Builder
import SCons.Action
import os
import os.path
from time import strftime, gmtime

from iotilepcb.drivers.eagle import *
from iotilecore.exceptions import BuildError

#FIXME: Replace this to include the actual schematic rather than just the board file
def build_pcb(target, source, env):
	board = EAGLECADReader([str(source[0])], [source[0]]).block
	cam_driver = EAGLECAMDriver(board)

	basedir = os.path.dirname(str(target[0]))

	if len(board.get_attribute('attrib:name', '')) == 0:
		raise BuildError("Cannot build pcb without a part name")

	outdir = os.path.join(basedir, board.get_attribute('attrib:name', ''))
	cam_driver.build_production(outdir)

	with open(str(target[0]), 'w') as f:
		f.write("Build Timestamp: %s" % strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime()))

def pcb_generator(source, target, env, for_signature):
	return SCons.Action.Action(build_pcb, "Building production files for pcb '%s'" % os.path.basename(str(source[0])))

def pcb_emit_int_files(target, source, env):
	board = EAGLECADReader([str(source[0])], [source[0]]).block
	cam_driver = EAGLECAMDriver(board)
	cam_driver.dry_run = True

	basedir = os.path.dirname(str(target[0]))
	if len(board.get_attribute('attrib:name', '')) == 0:
		raise BuildError("Cannot build pcb without a part name")

	outdir = os.path.join(basedir, board.get_attribute('attrib:name', ''))
	created = cam_driver.build_production(outdir)
	
	return target + created, source

_build_pcb = SCons.Builder.Builder(
	generator = pcb_generator,
	emitter = pcb_emit_int_files
	)

def generate(env):
	env['BUILDERS']['build_pcb'] = _build_pcb

def exists(env):
	return 1
