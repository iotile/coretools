#xc8_compiler.py
#SCons Builder Actions for the XC8 PIC compiler

import SCons.Builder
import os.path
import sys
from utilities import build_includes

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from pymomo.utilities.paths import convert_path	


def xc8_generator(source, target, env, for_signature):
	"""
	Create an XC8 command line using the parameter defined in 
	the environment
	"""

	arch = env['ARCH']

	incs = []

	args = ['xc8']

	if 'INCLUDE' in env:
		incs = build_includes(env['INCLUDE'])

	src = map(lambda x: convert_path(str(x)), source)
	out = ['-o' + str(target[0])]

	args.extend(make_chip(env))

	if 'XC8FLAGS' in env:
		args.extend(env['XC8FLAGS'])

	args.extend(incs)
	args.extend(make_rom(env))
	args.extend(make_ram(env))
	args.extend(src)
	args.extend(out)

	args = filter(lambda x: x != "", args)

	return " ".join(args)

def xc8_emit_int_files(target, source, env):
	targetdir = str(target[0].get_dir())

	intfiles = map(lambda x: make_int_files(x, targetdir), source)

	intfiles = reduce(lambda x,y: x+y, intfiles, [])

	target += intfiles + make_int_target_files(target[0])

	#Application modules have their own startup.as as a source file
	if "NO_STARTUP" in env:
		return target, source

	target += map(lambda x: os.path.join(targetdir, x), ['startup.lst', 'startup.obj', 'startup.rlf'])
	target += map(lambda x: os.path.join(targetdir, x), ['startup.as'])

	return target, source

def make_chip(env):
	return ['--chip=%s' % env['ARCH'].property('xc8_target')]

def make_rom(env):
	romstart = 0
	romend = -1
	if 'ROMSTART' in env:
		romstart = env['ROMSTART']

	if 'ROMEND' in env:
		romend = env['ROMEND']

	exclude = ","

	if 'ROMEXCLUDE' in env:
		exclude += ",".join(["-%x-%x" % (x[0],x[1]) for x in env['ROMEXCLUDE']])

	if exclude == ",":
		exclude = ""

	ranges = make_pages([romstart, romend])

	#No rom change specified
	#if romstart == 0 and romend == -1:
	#	return [""]

	ranges_txt = ",".join(["%x-%x" % (x[0], x[1]) for x in ranges])

	if romstart >= 0 and romend > 0:
		return ["--ROM=%s" % ranges_txt + exclude]

	raise ValueError("Unknown ROM Range Values: (%x, %x)" % (romstart, romend))	

def same_page(rom, pagesize=2048):
	startp = rom[0] / pagesize
	endp = rom[1] / pagesize

	if startp == endp:
		return True

	return False

def make_pages(rom, pagesize=2048):
	"""
	Take in a contiguous rom range (low, high) and return it divided on page boundaries.
	"""

	if same_page(rom, pagesize):
		return [rom]

	working = [rom[0], rom[1]]
	ranges = []

	while not same_page(working):
		startp = working[0]/pagesize
		enda = (startp + 1)*pagesize - 1

		ranges.append((working[0], enda))
		working[0] = enda+1

	ranges.append(working)

	return ranges


def make_ram(env):
	args = ['default']
	if 'RAMEXCLUDE' in env:
		exc = map(lambda x:"-{:x}-{:x}".format(x[0],x[1]), env['RAMEXCLUDE'])
		args.extend(exc)

	if 'RAMINCLUDE' in env:
		inc = map(lambda x:"+{:x}-{:x}".format(x[0],x[1]), env['RAMINCLUDE'])
		args.extend(inc)

	ramstatement = ",".join(args)

	return ['--RAM=%s' % ramstatement]

def make_int_files(cfile, folder):
	"""
	Given an Scons node representing a c or as file, create the xc8 intermediate targets
	"""
	name,ext = os.path.splitext(os.path.basename(str(cfile)))

	ints = []

	if ext == ".c":
		ints = [name + '.d', name + '.p1', name + '.pre']
	elif ext == ".as":
		ints = [name + '.d', name + '.lst', name + '.pre', name + '.obj', name + '.rlf']

	return map(lambda x: os.path.join(folder, x), ints)

def make_int_target_files(target):
	name,ext = os.path.splitext(os.path.basename(str(target)))
	outdir = str(target.get_dir())

	return map(lambda x: os.path.join(outdir, x), [name+'.as', name+'.cmf',name+'.cof',name+'.hxl',name+'.sdb',name+'.sym', name + '.lst', name + '.obj', name + '.rlf'])


_xc8_hex = SCons.Builder.Builder(
	generator = xc8_generator,
	emitter = xc8_emit_int_files)

def generate(env):
	env['BUILDERS']['xc8'] = _xc8_hex

def exists(env):
	return 1