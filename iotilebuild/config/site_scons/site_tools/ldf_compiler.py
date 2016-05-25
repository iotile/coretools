# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#ldf_compiler.py
#SCons Builder Action for creating header files from Log Definition Files

import SCons.Builder
import os.path
from iotilecore.syslog.descriptor import LogDefinitionMap
from iotilebuild.utilities.template import RecursiveTemplate
import shutil
from pkg_resources import resource_filename, Requirement

def ldf_create_header(target, source, env):
	"""
	Generate a header file with these log statements
	"""

	ldf = LogDefinitionMap()
	chip = env['ARCH']
	for src in source:
		ldf.add_ldf(str(src))

	name = os.path.basename(str(target[0]))
	name = name.replace(' ', '_').replace('.', '_')

	vals = {"k"+v.name: "{0:#x}".format(h)+"UL"  for h,v in ldf.entries.iteritems()}

	templ = RecursiveTemplate('logdefinitions.h', resource_filename(Requirement.parse("iotilebuild"), "iotilebuild/config/templates"))
	templ.add({'messages': vals, 'sources': ldf.sources, 'name': name})
	out = templ.format_temp()

	shutil.move(out, str(target[0]))

_ldf_obj = SCons.Builder.Builder(
	action = ldf_create_header,
	suffix='.h')

def generate(env):
	env['BUILDERS']['ldf_compiler'] = _ldf_obj

def exists(env):
	return 1
