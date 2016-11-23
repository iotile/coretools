# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.


import os.path
import sys
import subprocess
import functools
import platform
import os

from pkg_resources import resource_filename, Requirement

def settings_directory():
	"""
	Find a per user settings directory that is appropriate for each
	type of system that we are installed on.
	"""

	system = platform.system()

	basedir = None

	if system == 'Windows':
		if 'APPDATA' in os.environ:
			basedir = os.environ['APPDATA']
	elif system == 'Darwin':
		basedir = os.path.expanduser('~/Library/Preferences')

	#If we're not on Windows or Mac OS X, assume we're on some
	#kind of posix system where the appropriate place would be
	#~/.config
	if basedir is None:
		basedir = os.path.expanduser('~')
		basedir = os.path.join(basedir, '.config')

	settings_dir = os.path.abspath(os.path.join(basedir, 'IOTile-Core'))
	if not os.path.exists(settings_dir):
		os.makedirs(settings_dir, 0755)

	return settings_dir

def config_directory():
	return resource_filename(Requirement.parse("iotilecore"), "iotilecore/config")

def template_directory():
	return os.path.join(data_directory(), 'templates')

def memoize(obj):
	cache = obj.cache = {}

	@functools.wraps(obj)
	def memoizer(*args, **kwargs):
		key = str(args) + str(kwargs)
		if key not in cache:
			cache[key] = obj(*args, **kwargs)
		return cache[key]
	
	return memoizer

@memoize
def convert_path(path):
	"""
	If we are running on cygwin and passing an absolute path to a utility that is not cygwin
	aware, we need to convert that path to a windows style path. 
	"""

	if not os.path.isabs(path):
		return '"' + path + '"'

	if sys.platform == 'cygwin':
		out = subprocess.check_output(['cygpath', '-mw', path])
		out = out.lstrip().rstrip()
		return '"' + out + '"'

	return '"' + path + '"'
