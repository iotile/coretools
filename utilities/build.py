#build.py
#Return the build settings json file.

import json as json
from paths import MomoPaths
import os.path

def load_settings():
	paths = MomoPaths()
	filename = os.path.join(paths.config,'build_settings.json')

	with open(filename,'r') as f:
		return json.load(f)

	ValueError('Could not load global build settings file (config/build_settings.json)')

def load_chip_info(chip):
	"""
	Load chip info from chip_settings dictionary in build_settings.json
	"""
	conf = load_settings()
	settings = conf['mib12']['chip_settings'][chip]

	aliases = []
	if 'aliases' in settings:
		aliases = settings['aliases']

	default = conf['mib12']['default_settings'].copy()
	chip_info = merge_dicts(default, settings)

	return (aliases, chip_info)

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