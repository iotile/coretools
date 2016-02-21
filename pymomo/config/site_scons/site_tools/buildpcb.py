import SCons.Builder
import SCons.Action
import os
import os.path
from time import strftime, gmtime

from pymomo.pcb.board import CircuitBoard
from pymomo.pcb.production import ProductionFileGenerator

def build_pcb(target, source, env):
	"""
	Given two source files, the first being the mib12_executive and the second
	being an application hex, merge the two into a complete application hex
	"""

	board = CircuitBoard(str(source[0]))

	errors = board.get_errors()
	if len(errors) > 0:
		raise BuildError("PCB CAD data contained errors, cannot build production data", errors=errors)

	for warning in board.get_warnings():
		print "WARNING: (pcb build process) %s" % warning

	basedir = os.path.dirname(str(target[0]))
	board.generate_production(basedir)

	with open(str(target[0]), 'w') as f:
		f.write("Build Timestamp: %s" % strftime("%a, %d %b %Y %H:%M:%S +0000", gmtime()))

def pcb_generator(source, target, env, for_signature):
	return SCons.Action.Action(build_pcb, "Building production files for pcb '%s'" % os.path.basename(str(source[0])))

def pcb_emit_int_files(target, source, env):
	board = CircuitBoard(str(source[0]))

	prod = ProductionFileGenerator(board, dry_run=True)

	basedir = os.path.dirname(str(target[0]))
	prod.build_production(None, basedir)

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
