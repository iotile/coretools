#gpsim_runner.py

import SCons.Builder
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from pymomo.utilities import config


run_gpsim = SCons.Builder.Builder(
	action = 'gpsim -c $SOURCE -i > /dev/null'
	)

def generate(env):
	env['BUILDERS']['gpsim_run'] = run_gpsim

def exists(env):
	return 1