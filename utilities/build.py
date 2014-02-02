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