#board.py
#TODO
# - check for location of eagle in standard locations on Windows

import itertools
import xml.etree.cElementTree as ElementTree

import platform
import os
import subprocess

from part import part_from_board_element
from ..reference import PCBReferenceLibrary
from ..package import Package
from pymomo.exceptions import *

class EagleBoard:
	def __init__(self, brd_file):
		"""
		Create a Board from EAGLE Board file by parsing attribute tags embedded with the
		components.  Create different assembly variants for each different configuration
		specified in the file
		"""
		
		tree = ElementTree.parse(brd_file)
		if tree is None:
			raise DataError("Eagle board file does not contain valid XML", file=brd_file)

		root = tree.getroot()

		#Find all of the defined packages in this file
		packages =root.findall('.//packages')

		elems = root.find("./drawing/board/elements")
		if elems is None:
			raise DataError("Eagle board file does not contain a list of components", file=brd_file)

		parts = list(elems)

		unknown = []
		nopop = []
		constant = []
		variable = []
		variants = find_variants(root)

		all_vars = set(variants)

		#Create a part object for each part that has a valid digikey-pn
		#If there are multiple digikey part numbers, create a part for each one
		for part in parts:			
			valid_part = False
			found_vars = set()
			nopop_vars = set()

			for v in variants:
				p,found = part_from_board_element(part, v, packages)
				if p and found:
					variable.append( (v, p) )
					found_vars.add(v)
					valid_part = True
				elif found:
					#If this part has digipn == "" or Populate=no, then it should not be populated in this variant
					valid_part = True
					nopop_vars.add(v)
					nopop.append(part.get('name',"Unknown Name"))

			#See if this is a constant part (with no changes in different variants)
			p,found = part_from_board_element(part, "", packages)
			if p and len(found_vars) == 0 and len(nopop_vars) == 0:
				constant.append(p)
				valid_part = True
			elif p and len(found_vars) != len(all_vars):
				#there are some variants that want the default part and some that want a change
				for var in (all_vars - found_vars) - nopop_vars:
					variable.append( (var, p) )
					valid_part = True

			#Make sure this part has information for at least one assembly variant
			if not valid_part:
				unknown.append(part.get('name',"Unknown Name"))

		vars = {}
		#Create multiple variants
		for var in variants:
			vars[var] = constant + filter_sublists(variable, var)

		props = {}
		props['company'] = find_attribute(root, 'COMPANY', None)
		props['part'] = find_attribute(root, 'PARTNAME', None)
		props['width'] = find_attribute(root, 'WIDTH', None)
		props['height'] = find_attribute(root, 'HEIGHT', None)
		props['units'] = find_attribute(root, 'DIM_UNITS', None)
		props['revision'] = find_attribute(root, 'REVISION', None)
		props['no_populate'] = nopop
		props['unknown_parts'] = unknown
		props['variants'] = vars
		props['fab_engine'] = 'eagle' #Used by production.py to locate the templates for gerber generation
		props['fab_template'] = find_attribute(root, 'FAB_TEMPLATE', None)
		
		self.data = props
		self.file = brd_file

	def start_update(self):
		"""
		Open the underlying file for appending additional attributes

		Returns an opaque datatype that should be passed to set_metadata.
		"""

		tree = ElementTree.parse(self.file)
		if tree is None:
			raise DataError("Eagle board file does not contain valid XML", file=brd_file)

		return tree

	def finish_update(self, handle):
		"""
		Save the changes to the board file specified in handle.

		handle must be the result of a call to start_update
		"""

		handle.write(self.file)		

	def set_metadata(self, part, variant, key, value, handle=None):
		"""
		Update this board file with additional attributes.

		The board must be reloaded for the attributes to be visible.
		"""

		if handle is None:
			tree = self.start_update()
			root = tree.getroot()
		else:
			root = handle.getroot()

		element = root.find(".//element[@name='%s']" % part.name)
		if element is None:
			raise ArgumentError("Part was not found in board to update")

		att_name = key.upper()

		if att_name not in set(['MANU', 'MPN', 'DIST', 'DIST-PN', 'DIGIKEY-PN', 'FOOTPRINT', 'DESCRIPTION']):
			raise ArgumentError("attempting to set unknown metadata attribute", file=self.file, attribute=att_name, value=value, variant=variant)

		if variant is not None and variant != 'MAIN':
			att_name += '-%s' % variant.upper()

		att_elem = element.find("./attribute[@name='%s']" % att_name)
		if att_elem is not None:
			att_elem.set('value', value.upper())
		else:
			x = element.get('x', '0.0')
			y = element.get('y', '0.0')

			#Add in other default attributes for this xml element.
			attribs = {	'x': x, 'y': y, 'name': att_name, 'value': value.upper(),
						'size': "1.778", 'layer': "27", 'display': "off"}

			ElementTree.SubElement(element, 'attribute', **attribs)

		#Update the file with the modification if we were called in standalone mode
		if handle is None:
			tree.write(self.file)

	def build_production_file(self, path, layers, type, **kwargs):
		"""
		Use the data in this board file to produce Gerbers and Excellon files

		layers should be the eagle layers to include in the file
		type should be gerber, excellon or drawing
		optional kwargs may be supported in the future to adjust output
		"""

		#Options from EAGLE's built in gerber file for producing 2 layer boards
		#and argument names from EAGLE -? command
		args = ['-X', '-f+', '-c+', '-O+']

		if type == 'gerber':
			args.append('-dGERBER_RS274X')
		elif type == 'excellon':
			args.append('-dEXCELLON')
		elif type == 'drawing':
			args.append('-dPS')
			args.append('-h11')
			args.append('-w7.75')
			args.append('-s2.5')
		else:
			raise ArgumentError("Invalid type specified for production file (must be gerber, excellon or drawing)",  type=type)

		args.append('-o%s' % path)
		args.append(self.file)

		for layer in layers:
			args.append(layer)

		self._execute_eagle(args)

	def _find_eagle(self):
		"""
		Try to find the eagle executable on this system.

		If it's in the path, just return that, otherwise search in standard
		locations on each architecture or fail.
		"""

		from distutils.spawn import find_executable

		if platform.system() == 'Darwin':
			eagle = find_executable('EAGLE')
			if eagle is not None:
				return eagle

			entries = os.listdir('/Applications')
			possible_eagles = filter(lambda x: x.startswith('EAGLE-') and os.path.isdir(os.path.join('/Applications', x)), entries)

			#Try to get the latest EAGLE version if there are multiple installed
			try:
				possible_eagles.sort(key=lambda x: map(int, x[6:].split('.')))

				eagle_dir = possible_eagles[-1]
				eagle_path = os.path.join('/Applications', eagle_dir, 'EAGLE.app', 	'Contents', 'MacOS', 'EAGLE')

				if os.path.isfile(eagle_path) and os.access(eagle_path, os.X_OK):
					return eagle_path
			except ValueError:
				#Value errors mean we could not convert the version string to an int, indicating that it wasn't in the form X.Y.Z
				#ignore this error and just say we couldn't find EAGLE since an eagle directory without an X.Y.Z form could be a
				#different program altogether.
				pass
		elif platform.system() == 'Windows':
			eagle = find_executable('EAGLECON')
			if eagle is not None:
				return eagle

			#TODO: Check for eagle location on windows and autofind
			#Check for program files directory in 32 or 64 bit mode like so:
			#http://stackoverflow.com/questions/1283664/python-get-wrong-value-for-os-environprogramfiles-on-64bit-vista
		else:
			#Otherwise assume that Eagle will be in $PATH
			eagle = find_executable('EAGLECON')
			if eagle is not None:
				return eagle

		raise EnvironmentError("could not find installed version of Cadsoft EAGLE", suggestion='install EAGLE and add it to your $PATH')

	def _execute_eagle(self, args):
		eagle = self._find_eagle()
		
		#TODO: Check what kinds of exceptions this can throw
		with open(os.devnull, 'wb') as DEVNULL:
			subprocess.check_call([eagle] + args, stdout=DEVNULL, stderr=DEVNULL)


#Helper functions
def remove_prefix(s, prefix):
	if not s.startswith(prefix):
		return s

	return s[len(prefix):]

def filter_sublists(master, key):
	"""
	Given a list of lists where each of the sublist elements are tuples (key, value),
	return a concatenated list of all values in tuples that match key
	"""

	concat = itertools.chain(master)

	filtered = filter(lambda x: x[0] == key, concat)

	return map(lambda x:x[1], filtered)

MISSING = object()
def find_attribute(root, name, default=MISSING):
	attr = root.find(".//attribute[@name='%s']" % name)
	if attr is None:
		if default is not MISSING:
			return default

		raise DataError("required board attribute not found", name=name)

	return attr.get('value')

def find_variants(root):
	vars = root.findall(".//attribute[@value='%s']" % 'ASSY-VARIANT')

	if len(vars) == 0:
		return ["MAIN"]
	else:
		return map(lambda x: x.get('name'), vars)
