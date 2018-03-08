# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

#config.py

from builtins import range
import os
import json

class ConfigFile:
	"""
	A simple wrapper around a json config file with a local and global version
	the local version always overrides the global version.
	"""

	def __init__(self, base_dir, name, require_local=False):
		localpath = os.path.join(base_dir, name +'.local.json')
		globalpath = os.path.join(base_dir, name + '.global.json')

		conf = {}
		localconf = None
		try:
			with open(globalpath, 'r') as f:
				conf = json.load(f)
		except IOError:
			pass #global file can not exist

		try:
			with open(localpath, 'r') as f:
				localconf = json.load(f)
		except IOError:
			if require_local:
				raise ValueError('Local settings file does not exist and is required: %s' % name +'.local.json')

		if localconf is not None:
			merge_dicts(conf, localconf)

		self.conf = conf

	def __getitem__(self, path):
		"""
		Given a path specifying subdictionaries in this config dictionary,
		with each key separated by a /, return the value indicated.  It must
		exist.
		"""

		keys = path.split('/')

		val = self.conf[keys[0]]

		for i in range(1, len(keys)):
			val = val[keys[i]]

		return val


#from http://stackoverflow.com/questions/7204805/python-dictionaries-of-dictionaries-merge
def merge_dicts(a, b):
    "merges b into a"

    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge_dicts(a[key], b[key])
            else:
            	a[key] = b[key]
        else:
            a[key] = b[key]

    return a
