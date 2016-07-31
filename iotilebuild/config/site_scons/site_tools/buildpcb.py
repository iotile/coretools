# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import SCons.Builder
import SCons.Action
import os
import os.path
from time import strftime, gmtime

from iotilecore.pcb.board import CircuitBoard
from iotilecore.pcb.production import ProductionFileGenerator
from iotilecore.exceptions import BuildError

def build_pcb(target, source, env):
	board = CircuitBoard(str(source[0]))

	errors = board.get_errors()
	if len(errors) > 0:
		raise BuildError("PCB CAD data contained errors, cannot build production data", errors=errors)

	for warning in board.get_warnings():
		print "WARNING: (pcb build process) %s" % warning

	basedir = os.path.dirname(str(target[0]))

	if len(board.part) == 0:
		raise BuildError("Cannot build pcb without a part name")

	outdir = os.path.join(basedir, board.part)
	board.generate_production(outdir)

	with open(str(target[0]), 'w') as f:
		f.write("Build Timestamp: %s" % strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime()))

def pcb_generator(source, target, env, for_signature):
	return SCons.Action.Action(build_pcb, "Building production files for pcb '%s'" % os.path.basename(str(source[0])))

def pcb_emit_int_files(target, source, env):
	board = CircuitBoard(str(source[0]))

	prod = ProductionFileGenerator(board, dry_run=True)

	basedir = os.path.dirname(str(target[0]))
	if len(board.part) == 0:
		raise BuildError("Cannot build pcb without a part name")

	outdir = os.path.join(basedir, board.part)
	board.generate_production(outdir)

	created = prod.created_files
	
	return target + created, source

_build_pcb = SCons.Builder.Builder(
	generator = pcb_generator,
	emitter = pcb_emit_int_files
	)

def generate(env):
	env['BUILDERS']['build_pcb'] = _build_pcb

def exists(env):
	return 1
