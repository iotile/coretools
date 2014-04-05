#part.py

import re
import reference

known_types = {
	"C": "capacitor",
	"R": "resistor",
	"D": "diode",
	"JP": "connector",
	"U": "ic",
	"XTAL": "crystal",
	"L": "inductor",
	"LED": "led"
}

class_table = {
	""
}

class Part:
	"""
	An electronic component.
	"""

	ref = reference.PCBReferenceLibrary()

	@staticmethod
	def FromBoardElement(elem, variant, packages):
		"""
		Create a Part object from an element in an EAGLE board file. 
		pn_attrib specifies the attribute name that contains the correct
		manufacturer or distributor part number for this part.

		@TODO:
			- parse pn_attrib to determine whether its a distributor pn or a manu pn
			and set attributes accordingly
		"""

		pkg = elem.get('package', 'Unknown Package')
		pkg_info = None

		if pkg in packages:
			pkg_info = packages[pkg]

		name = elem.get('name', 'Unnamed')
		value = elem.get('value', 'No Value')

		#allow overriding this package with a custom attribute
		pkg = find_attribute(elem, 'FOOTPRINT', variant, pkg)
		desc = find_attribute(elem, 'DESCRIPTION', variant, None)
		pop_attr = find_attribute(elem, 'POPULATE', variant, "yes")

		if pop_attr.lower() == "no":
			return None, True
		elif pop_attr != "yes":
			raise ValueError("Unknown value in POPULATE attribute in element %s: %s" % (name, pop_attr))

		#Only keep the value for part types where that is meaningful
		if not Part.ref.has_value(name):
			value = None

		(manu, mpn) = find_mpn(elem, variant)
		digipn = find_digipn(elem, variant)

		if (mpn is not None and manu is not None) or (digipn is not None and digipn != ""):
			return Part(name, pkg, digipn=digipn, mpn=mpn, manu=manu, value=value, desc=desc, pkg_info=pkg_info), True
		elif mpn == "" or digipn == "":
			return None, True

		return None, False

	def __init__(self, name, package, mpn=None, manu=None, digipn=None, value=None, desc=None, pkg_info=None):
		"""
		Create a part object from the data passed
		"""

		self.name = name
		self.package = package
		self.mpn = mpn
		self.manu = manu
		self.value = value
		self.digipn = digipn
		self.desc = desc
		self.pkg_info = pkg_info

		#If no description is given try creating a generic one based on the type of the part (resistor, etc)
		if self.desc is None:
			self.desc = Part.ref.find_description(self.name, self.value)

	def _parse_type(self, type):
		refs = type.split(',')
		alpha_pat = re.compile('[a-zA-Z]+')

		prefix = re.match(alpha_pat, refs[0])

		if prefix is None:
			return "unknown"

	def unique_id(self):
		"""
		Return a unique key that can be used to group multiple parts that are identical.
		"""

		if self.manu and self.mpn:
			return "%s_%s" % (self.manu, self.mpn)

		return "Digikey_%s" % self.digipn

	def package_info(self):
		if self.pkg_info is None:
			return {'pins': 0, 'pads': 0}

		return {'pins': self.pkg_info.num_pins, 'pads': self.pkg_info.num_pads}

def attrib_name(name, variant):
	if variant == "MAIN" or variant == "":
		return name

	return name + '-' + variant

def find_attribute(part, name, variant, default=None):
	"""
	Find the attribute corresponding the given variant, or if that doesn't exist, 
	the value corresponding to MAIN, otherwise return the given default
	"""

	attrib_var = part.find("./attribute[@name='%s']" % attrib_name(name, variant))
	attrib_main = part.find("./attribute[@name='%s']" % attrib_name(name, 'MAIN'))

	if attrib_var is not None:
		return attrib_var.get('value')

	if attrib_main is not None:
		return attrib_main.get('value')

	return default

def find_mpn(part, variant):
	"""
	See if this part has the variables MPN[-variant] and MANU[-variant] defined
	return None if either is undefined.  Otherwise return the tuple (manu, mpn)
	"""

	mpn = part.find("./attribute[@name='%s']" % attrib_name('MPN', variant))
	manu = part.find("./attribute[@name='%s']" % attrib_name('MANU', variant))

	if mpn is None or manu is None:
		return (None, None)

	return (manu.get('value', 'Unknown'), mpn.get('value', 'Unknown'))

def find_digipn(part, variant):
	pn_elem = part.find("./attribute[@name='%s']" % attrib_name('DIGIKEY-PN', variant))

	if pn_elem is None:
		return None

	return pn_elem.get('value', "")