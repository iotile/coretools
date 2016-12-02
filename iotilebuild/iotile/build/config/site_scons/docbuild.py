from string import Template
import os
from pkg_resources import resource_filename, Requirement
from iotile.build.utilities.template import RecursiveTemplate

def generate_doxygen_file(output_path, iotile):
	"""Fill in our default doxygen template file with info from an IOTile

	This populates things like name, version, etc.

	Arguments:
		output_path: 	a string path for where the filled template should go
		iotile: An IOTile object that can be queried for information
	"""

	input_template = os.path.join(resource_filename(Requirement.parse("iotile-build"), "iotile/build/config"), 'templates', 'doxygen.txt')

	with open(input_template, "r") as f:
		temp = Template(f.read())

	mapping = {}

	mapping['short_name'] = iotile.short_name
	mapping['full_name'] = iotile.full_name
	mapping['authors'] = iotile.authors
	mapping['version'] = iotile.version

	with open(output_path, "w") as f:
		f.write(temp.safe_substitute(mapping))

def doxygen_source_path():
	return os.path.abspath(os.path.join(resource_filename(Requirement.parse("iotile-build"), "iotile/build/config"), 'templates', 'doxygen.txt'))
