#utilities.py

from SCons.Script import *
from SCons.Environment import Environment
import os
import fnmatch
import json as json
import sys
import os.path
import pic12
import StringIO

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pymomo.utilities import build
from pymomo.mib.config12 import MIB12Processor

def find_files(dirname, pattern):
	"""
	Recursively find all files matching pattern under path dirname
	"""

	matches = []
	for root, dirnames, filenames in os.walk(dirname, followlinks=True):
		print dirnames, filenames
		for filename in fnmatch.filter(filenames, pattern):
			matches.append(os.path.join(root,filename))

	return matches

def build_includes(includes):
	if isinstance(includes, basestring):
		includes = [includes]

	return ['-I"%s"' % x for x in includes]

def build_libdirs(libdirs):
	if isinstance(libdirs, basestring):
		libdirs = [libdirs]

	return ['-L"%s"' % x for x in libdirs]

def build_staticlibs(libs, chip):
	if isinstance(libs, basestring):
		libs = [libs]

	processed = []
	for lib in libs:

		#Allow specifying absolute libraries that don't get architectures
		#appended
		if lib[0] == '#':
			processed.append(lib[1:])
		else:
			#Append chip type and suffix
			proclib = "%s_%s" % (lib, chip.arch_name())
			processed.append(proclib)

	return ['-l%s' % x for x in processed]

def build_defines(defines):
	return ['-D%s=%s' % (x,str(y)) for x,y in defines.iteritems()]

def get_family(fam, modulefile=None):
	return build.ChipFamily(fam, modulefile=modulefile)

class BufferedSpawn:
	def __init__(self, env, logfile):
		self.env = env
		self.logfile = logfile

		self.stderr = StringIO.StringIO()
		self.stdout = StringIO.StringIO()

	def spawn(self, sh, escape, cmd, args, env):
		cmd_string = " ".join(args)

		print cmd_string
		self.stdout.write(cmd_string)
		
		try:
			retval = self.env['PSPAWN'](sh, escape, cmd, args, env, sys.stdout, sys.stderr)
		except OSError, x:
			if x.errno != 10:
				raise x

			print 'OSError Ignored on command: %s' % cmd_string

		return retval
