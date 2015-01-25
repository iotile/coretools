#logical_part.py

import re
from pymomo.pcb import reference

def convert(arg, **kwargs):
	if arg is None:
		return None

	if isinstance(arg, Part):
		return arg

	elif isinstance(arg, dict):
		return Part(**arg)

	raise ValueError("Creating a logical_part from any type other than a Part object is not supported")

def validate_matchable(arg, **kwargs):
	if not arg.matchable():
		raise ValueError("part does not have enough metadata to be matchable")

def default_formatter(arg, **kwargs):
	return str(arg)

class Part:
	"""
	An electronic component.
	"""

	ref = reference.PCBReferenceLibrary()

	def __init__(self, name, package, placement, mpn=None, manu=None, dist=None, distpn=None, value=None, desc=None):
		"""
		Create a part object from the data passed
		"""

		self.name = name
		self.package = package
		self.mpn = mpn
		self.manu = manu
		self.value = value
		self.distpn = distpn
		self.dist = dist
		self.placement = placement
		self.desc = desc

		#If no description is given try creating a generic one based on the type of the part (resistor, etc)
		if self.desc is None:
			self.desc = Part.ref.find_description(self.name, self.value)

	def matchable(self):
		"""
		Return true if this part has enough information to be matched and priced online
		"""

		return self.name != None and ((self.manu != None and self.mpn != None) or (self.dist != None and self.distpn != None))

	def placeable(self):
		"""
		Return true if this part has enough information to be physically located on a board
		"""

		return (self.package != None and self.placement != None)

	def complete(self):
		"""
		Return true if this part has all required information for BOM matching and placing
		"""

		return self.matchable() and self.placeable()

	def unique_id(self):
		"""
		Return a unique key that can be used to group multiple parts that are identical.
		"""

		if self.manu and self.mpn:
			return "%s_%s" % (self._canonicalize(self.manu), self._canonicalize(self.mpn))

		return "%s_%s" % (self._canonicalize(self.dist), self._canonicalize(self.distpn))

	def _canonicalize(self, string):
		"""
		Given a string, remove all spaces, - and _ and make it lower case.
		"""

		s = string.lower()
		return s.replace(' ', '').replace('-','').replace('_','')

	def __str__(self):
		string = ""
		string += "Part %s" % str(self.name) + '\n'
		string += " Manufacturer: " + str(self.manu) + '\n'
		string += " MPN: " + str(self.mpn) + '\n'
		string += " Distributor: " + str(self.dist) + '\n'
		string += " Distributor PN: " + str(self.distpn) + '\n'
		string += " Package: " + str(self.package) + '\n'
		string += " Location: " + str(self.placement) + '\n'
		string += " Description: " + str(self.desc)
		
		return string

	def __eq__(self, other):
		try:
			return self.name == other.name and self.package == other.package and self.mpn == other.mpn and \
			self.manu == other.manu and self.value == other.value and self.distpn == other.distpn and \
			self.dist == other.dist and self.placement == other.placement and self.desc == other.desc
		except AttributeError:
			raise False
