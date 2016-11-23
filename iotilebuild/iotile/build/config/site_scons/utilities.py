# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#utilities.py

from SCons.Script import *
from SCons.Environment import Environment
import os
import fnmatch
import json as json
import sys
import os.path
import StringIO
from iotile.build.build import build


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

def join_path(path):
	"""
	If given a string, return it, otherwise combine a list into a string
	using os.path.join
	"""

	if isinstance(path, basestring):
		return path
	
	return os.path.join(*path)

def build_defines(defines):
	return ['-D%s=%s' % (x,str(y)) for x,y in defines.iteritems()]

def get_family(modulefile):
	return build.ArchitectureGroup(modulefile)
