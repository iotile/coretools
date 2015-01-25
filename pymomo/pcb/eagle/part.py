#Routines for building part objects from eagle board files
from pint import UnitRegistry
from pymomo.exceptions import *
from pymomo.utilities.typedargs import type_system

from ..package import Pad, Pin, Package, Placement

ureg = UnitRegistry()

def part_from_board_element(elem, variant, packages):
	"""
	Create a Part object from an element in an EAGLE board file. 

	Automatically extract all of the known attributes of the part to fill in the
	reference identifier, package information, number of pads/pins, footprint,
	description, etc.

	packages should be a list of XML elements corresponding to the various lists of packages 
	for this board.

	Returns a tuple of Part,Boolean
	The Part describes this part and may be None if it is not populated in this variant
	The Boolean is true is this part is valid and populated in this variant and false otherwise.
	"""

	pkg = elem.get('package', None)

	name = elem.get('name', 'No Name')
	value = elem.get('value', 'No Value')

	value_override = find_attribute(elem, 'VALUE', variant)
	if value_override is not None:
		value = value_override

	#allow overriding this package with a custom name
	pkgname = find_attribute(elem, 'FOOTPRINT', variant, pkg)
	if pkg is not None:
		pkg_info = find_package(packages, pkg, display_name=pkgname)
	else:
		pkg_info = Package(str(pkgname), [], [])

	desc = find_attribute(elem, 'DESCRIPTION', variant, None)
	pop_attr = find_attribute(elem, 'POPULATE', variant, "yes")
	
	if pop_attr.lower() == "no":
		return None, True
	elif pop_attr != "yes":
		raise ValidationError("Unknown value in POPULATE attribute in element %s: %s" % (name, pop_attr))

	manu, mpn = find_mpn(elem, variant)
	dist, distpn = find_distpn(elem, variant)

	#Get physical location information
	x = float(elem.get('x')) * ureg.millimeter
	y = float(elem.get('y')) * ureg.millimeter

	rot = elem.get('rot')
	if rot is None:
		rot = 0.0
	else:
		rot = float(elem.get('rot')[1:])			#Rotation is specified at R## where ## is the angle in degrees.

	placement = Placement(x, y, rot)

	if (mpn is not None and manu is not None) or (dist is not None and distpn is not None):
		args = {}
		args['name'] = name
		args['package'] = pkg_info
		args['placement'] = placement
		args['dist'] = dist
		args['distpn'] = distpn
		args['mpn'] = mpn
		args['manu'] = manu
		args['value'] = value
		args['desc'] = desc

		return type_system.convert_to_type(args, 'logical_part'), True

	return None, False

def attrib_name(name, variant):
	if variant == "MAIN" or variant == "":
		return name

	return name + '-' + variant

def find_attribute(part, name, variant, default=None):
	"""
	Find the attribute corresponding to the given variant, or if that doesn't exist, 
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

	mpn  = find_attribute(part, 'MPN', variant)
	manu = find_attribute(part, 'MANU', variant)

	if mpn is None or manu is None:
		return (None, None)

	return (manu, mpn)

def find_distpn(part, variant):
	"""
	Try to find a distributor part number for this part

	This can be specified either using a single combined attribute for Digikey
	parts (DIGIKEY-PN) or by using 2 attributes specifying the distributor and
	the part number (DIST and DIST-PN).  If any of these are blank, they are returned
	as None.
	"""

	#Look for a digikey pn attribute as a shortcut for digikey parts
	pn_elem = find_attribute(part, 'DIGIKEY-PN', variant)
	if pn_elem is not None:
		return ("Digikey", pn_elem)

	pn_elem = find_attribute(part, 'DIST-PN', variant)
	dist_elem = find_attribute(part, 'DIST', variant)

	dist = None
	pn = None

	if pn_elem is not None:
		pn = pn_elem
	if dist_elem is not None:
		dist = dist_elem

	return (dist, pn)

def find_package(packages, find_name, display_name):
	"""
	Create a Package object from the named package
	"""

	found = False

	for packagelist in packages:
		package = packagelist.find("./package[@name='%s']" % str(find_name))
		if package is not None:
			found = True
			break

	if found is False:
		raise ValidationError("Invalid board file, a package was used but not defined", name=find_name)

	eagle_pads = package.findall("./smd")
	eagle_pins = package.findall("./pad")

	pads = []
	pins = []

	#Eagle boards store all coordinates in mm regardless of how it is displayed
	for epad in eagle_pads:
		x = float(epad.get('x'))  * ureg.millimeter
		y = float(epad.get('y'))  * ureg.millimeter
		w = float(epad.get('dx')) * ureg.millimeter
		h = float(epad.get('dy')) * ureg.millimeter

		pad = Pad(x, y, w, h)
		pads.append(pad)

	for epin in eagle_pins:
		x = float(epin.get('x'))  * ureg.millimeter
		y = float(epin.get('y'))  * ureg.millimeter
		drill = float(epin.get('drill'))  * ureg.millimeter

		pin = Pin(x,y, drill)
		pins.append(pin)

	return Package(display_name, pins, pads)
