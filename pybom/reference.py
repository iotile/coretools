#reference.py
#A manager for reference information used in creating circuit board BOMs
#and production files

import json
import os.path
import re
import sys

from ..utilities.config import ConfigFile

data_file = ConfigFile('pcb_library')

class PCBReferenceLibrary:
	def __init__(self):
		self.lib = data_file

		self._import_packages()
		self._import_descriptions()
		self.valued_types = set(self.lib["types_with_values"])
		self._alpha_re = re.compile(r"^[a-zA-Z]*")

	def _import_packages(self):
		pkgs = self.lib['footprint_names']

		self.packages = {}

		for name,val in pkgs.iteritems():
			self.packages[name] = set(val)

	def _import_descriptions(self):
		self.descs = self.lib['description_templates']

	def find_description(self, name, value):
		"""
		Look to see if there is a template for generating the description
		of this piece based on its reference type R, C, etc and its value
		"""
		t = self._alpha_re.match(name)

		if t is None:
			return None

		cat = t.group(0)

		if cat in self.descs:
			return self.descs[cat].format(value=value)
		
		return None

	def has_value(self, name):
		"""
		Look up if this type has a meaningful value and return True if so, 
		otherwise False.
		"""
		
		t = self._alpha_re.match(name)

		if t is None:
			return False

		cat = t.group(0)

		if cat in self.valued_types:
			return True

		return False

	def find_package(self, pkg):
		"""
		Look for the footprint in our list of known packages.  Return a tuple
		of (package name, bool found).  
		"""
		for name, val in self.packages.iteritems():
			if pkg in val:
				return (name, True)

		return (pkg, False)