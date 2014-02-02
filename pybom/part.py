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
	def FromBoardElement(elem, variant):
		"""
		Create a Part object from an element in an EAGLE board file. 
		pn_attrib specifies the attribute name that contains the correct
		manufacturer or distributor part number for this part.

		@TODO:
			- parse pn_attrib to determine whether its a distributor pn or a manu pn
			and set attributes accordingly
		"""

		pkg = elem.get('package', 'Unknown Package')
		name = elem.get('name', 'Unnamed')
		value = elem.get('value', 'No Value')

		#allow overriding this package with a custom attribute
		pkg = find_attribute(elem, 'FOOTPRINT', variant, pkg)
		desc = find_attribute(elem, 'DESCRIPTION', variant, None)	

		#Only keep the value for part types where that is meaningful
		if not Part.ref.has_value(name):
			value = None

		(manu, mpn) = find_mpn(elem, variant)
		digipn = find_digipn(elem, variant)

		if (mpn is not None and manu is not None) or (digipn is not None and digipn != ""):
			return Part(name, pkg, digipn=digipn, mpn=mpn, manu=manu, value=value, desc=desc)

		return None

	def __init__(self, name, package, mpn=None, manu=None, digipn=None, value=None, desc=None):
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

	return pn_elem.get('value')