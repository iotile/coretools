#gpsim_runner.py

import SCons.Builder
import platform

#There is no /dev/null on Windows
if platform.system() == 'Windows':
	action = 'gpsim -c $SOURCE -i > NUL'
else:
	action = 'gpsim -c $SOURCE -i > /dev/null'

run_gpsim = SCons.Builder.Builder(
	action = action
	)

def generate(env):
	env['BUILDERS']['gpsim_run'] = run_gpsim

def exists(env):
	return 1