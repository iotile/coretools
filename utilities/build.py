#build.py
#Return the build settings json file.

import json as json
from paths import MomoPaths
import os.path
from pymomo.utilities import deprecated

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

class ChipSettings:
	"""
	A class that contains a dictionary of all the settings defined for
	a given chip in a ChipFamily.  The settings are a combination of
	default settings for the family which can be overwritten by chip
	specific settings.
	"""

	def __init__(self, name, settings, family, module=None):
		self.name = name

		#If we are passed in a module, merge in any module specific overrides
		if module is not None and name in module:
			self.settings = merge_dicts(settings, module[name])
		else:
			self.settings = settings

		self.family = family

	def build_dirs(self):
		"""
		Return the build directory hierarchy:
		Defines:
		- build: build/chip
		- output: build/output
		- test: build/test/chip
		where chip is the cannonical name for the chip passed in
		"""

		build = os.path.join('build', self.name)
		output = os.path.join('build', 'output')
		test = os.path.join('build', 'test', self.name)

		return {'build': build, 'output': output, 'test': test}

	def property(self, name, default=None):
		"""
		Get the value of the given property for this chip, using the default
		value if not found and one is provided.  If not found and default is None,
		raise an Exception.
		"""

		if name in self.settings:
			return self.settings[name]	
		
		if default is not None:
			return default

		raise ValueError("property %s not found for chip %s" % (name, self.name))

	def includes(self):
		"""
		Return all of the include directories for this chip as a list.
		"""

		paths = MomoPaths()
		base = paths.modules

		includes = []

		if "includes" in self.settings:
			includes += self.settings['includes']

		fullpaths = [os.path.normpath(os.path.join(base, x)) for x in includes + self.family.includes]
		return fullpaths


class ChipFamily:
	"""
	Given a family of chips that may be targeted together from the same source 
	code, load in the chip names and aliases and store it in a standardized
	fashion.  The data is loaded from config/build_settings.json.
	"""

	def __init__(self, surname):
		"""
		Build a ChipFamily from the family name, e.g. mib12, mib24
		"""

		settings = load_settings()
		if not surname in settings:
			raise ValueError("Could not find family %s in config file" % surname)

		family = settings[surname]


		self.aliases = {}
		self.module_targets = {}
		self.includes = []


		self._load_family(settings, surname)
		self._load_modules(family)
		self._load_module_overrides(family)

		if "includes" in family:
			self.includes = family['includes']

	def find(self, name, module=None):
		"""
		Find a given chip by one of its aliases. Returns a ChipSettings object.
		If kw module is passed, module specific overrides are added to the 
		ChipSettings object.
		"""

		if name not in self.aliases:
			raise KeyError("Could not find chip by alias %s" % name)

		target = self.aliases[name]
		chip = self.known_targets[target]

		overrides = {}
		if module in self.module_settings:
			overrides = self.module_settings[module]

		return ChipSettings(chip.name, chip.settings, self, overrides)

	def targets(self, module):
		"""
		Return a sequence of all of the targets for the specified module.
		Modules that have no entry in module_targets in build_setings.json
		target all family defined targets by default.
		"""

		if module in self.module_targets:
			return [self.find(x, module) for x in self.module_targets[module]]

		return [self.find(x, module) for x in self.known_targets.keys()]

	def for_all_targets(self, module, func):
		"""
		Call func once for all of the targets of this module 
		"""
		
		for target in self.targets(module):
			func(target)

	def _load_family(self, settings, surname):
		family = settings[surname]

		targets = family['known_targets']
		self.known_targets = {x: self._load_target(family, x) for x in targets}

	def _load_module_overrides(self, family):
		"""
		Modules can override chip specific definitions 
		"""

		if 'module_settings' not in family:
			self.module_settings = {}

		self.module_settings = {mod: settings for mod,settings in family['module_settings'].iteritems()}

	def _load_target(self, family, target):
		"""
		Load in the chip specific target information and aliases for the
		given target
		"""

		chip_settings = {}
		default = family['default_settings'].copy()

		if target in family['chip_settings']:
			chip_settings = family['chip_settings'][target]
			if "aliases" in chip_settings:
				for alias in chip_settings['aliases']:
					self.aliases[alias] = target

		self.aliases[target] = target

		chip_settings = merge_dicts(default, chip_settings)
		return ChipSettings(target, chip_settings, self)

	def _load_modules(self, family):
		if "module_targets" in family:
			for mod, targets in family['module_targets'].iteritems():
				self.module_targets[mod] = targets
