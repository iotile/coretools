#Objects for dealing with PCB packages, pads and pins

from pymomo.exceptions import *
from reference import PCBReferenceLibrary
import itertools

class Package:
	"""
	A pcb component package.

	This contains information on the pins and pads in the package
	as well as the package type.
	"""

	def __init__(self, name, pins, pads):
		"""
		Build a package from a name and a list of pins and pads

		- pins should be a list of Pin objects
		- pads should be a list of Pad objects
		- name should be an identifier that will let us look up information
		  about this package in our database of standard packages.
		"""

		ref = PCBReferenceLibrary()

		self.pins = pins
		self.pads = pads

		refined_name, found = ref.find_package(name)

		if found:
			self.name = refined_name
		else:
			self.name = name

	def __str__(self):
		return "%s Package (%d pins, %d pads)" % (self.name, len(self.pins), len(self.pads))

	def __eq__(self, other):
		try:
			if self.name != other.name:
				return False

			for p1, p2 in itertools.izip_longest(self.pins, other.pins, fillvalue=None):
				if p1 != p2:
					return False

			for p1, p2 in itertools.izip_longest(self.pads, other.pads, fillvalue=None):
				if p1 != p2:
					print p1
					print p2
					return False
		except AttributeError:
			return False

		return True

	def __ne__(self, other):
		return not self == other


class Pin:
	"""
	A through hole pin
	"""

	def __init__(self, x, y, drill=None, ring=None):
		if is_quantity(x) and is_quantity(y):
			self.x = x
			self.y = y
		else:
			raise ValidationError("pin position is not specified as a dimensioned quantity", x=x, y=y)

		if drill is not None and not is_quantity(drill):
			raise ValidationError("pin drill size is not specified as a dimensioned quantity", x=x, y=y)

		if ring is not None and not is_quantity(ring):
			raise ValidationError("pin annular ring is not specified as a dimensioned quantity", x=x, y=y)

		self.drill = drill
		self.ring = ring

	def __eq__(self, other):
		try:
			return self.x == other.x and self.y == other.y and self.drill == other.drill and self.ring == other.ring
		except AttributeError:
			return False

	def __ne__(self, other):
		return not self == other


class Pad:
	"""
	A surface mount pad
	"""

	def __init__(self, x, y, width, height):
		if is_quantity(x) and is_quantity(y):
			self.x = x
			self.y = y
		else:
			raise ValidationError("smt pad position is not specified as a dimensioned quantity", x=x, y=y)

		if is_quantity(width) and is_quantity(height):
			self.width = width
			self.height = height
		else:
			raise ValidationError("width and heigh is not specified as a dimensioned quantity", width=width, height=height)

	def __str__(self):
		return "SMT Pad at (%s, %s) size: (%s, %s)" % (str(self.x), str(self.y), str(self.width), str(self.height))

	def __eq__(self, other):
		try:
			return (self.x == other.x) and (self.y == other.y) and (self.width == other.width) and (self.height == other.height)
		except AttributeError:
			return False

	def __ne__(self, other):
		return not self == other

class Placement:
	"""
	A class describing the physical placement and rotation of a PCB component.
	"""

	def __init__(self, x, y, rotation=0.0):
		"""
		Store an x,y location and a rotation (in degrees)
		"""

		if is_quantity(x) and is_quantity(y):
			self.x = x
			self.y = y
		else:
			raise ValidationError("placement position is not specified as a dimensioned quantity", x=x, y=y)

		self.rotation = rotation

	def __eq__(self, other):
		try:
			return self.x == other.x and self.y == other.y and self.rotation == other.rotation
		except AttributeError:
			return False

	def __ne__(self, other):
		return not self == other

	def __str__(self):
		return "(%s, %s) rotated %d degrees" % (str(self.x), str(self.y), self.rotation)


def is_quantity(val):
	if hasattr(val, 'magnitude') and hasattr(val, 'units'):
		return True

	return False
