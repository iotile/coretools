# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#patch_mib12.py

import SCons.Builder

_patch_mib12 = SCons.Builder.Builder(
	action = 'patch_mib12_api.py $MIB_API_BASE $SOURCES $TARGET'
	)

def generate(env):
	env['BUILDERS']['patch_mib12'] = _patch_mib12

def exists(env):
	return 1