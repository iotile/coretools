#production.py
#A set of routines for building a set of production files for fabricating and assembling
#circuit boards

import os.path
import zipfile
from pymomo.exceptions import *
from pymomo.utilities.paths import MomoPaths
from datetime import date
import platform
import subprocess

class ProductionFileGenerator:
	"""
	Helpful routines for building production files for PCB fabrication and assembly
	"""

	def __init__(self, board):
		config = MomoPaths().config
		
		template_file = os.path.join(config, 'pcb', board.fab_engine + ".json")
		self.template = self._load_template(template_file, board.fab_template)
		self.board = board

	def save_readme(self, path):
		"""
		Create a README file for this board based on the information it contains
		and the template for the production files.
		"""

		basename = self._basename()

		with open(path, "w") as f:
			f.write("PCB Fabrication Files\n")
			f.write("%s\n" % self.board.company)
			f.write("Name: %s\n" % self.board.part)
			f.write("Revision: %s\n" % self.board.revision)
			f.write("Dimensions: %sx%s %s\n" % (self.board.width, self.board.height, self.board.units))
			f.write("Date Created: %s\n\n" % str(date.today()))
			f.write("Folder Contents:\n")

			for name, layer in self.template['layers'].iteritems():
				f.write("%s.%s: %s\n" % (basename, layer['extension'], name))

	def _build_production(self, outdir, layer):
		basename = self._basename()
		path = os.path.join(outdir, "%s.%s" %(basename, layer['extension']))


		self.board.board.build_production_file(path, layer['program_layers'], layer['type'])

		if 'remove' in layer:
			remname = "%s.%s" % (basename, layer['remove'])
			os.remove(os.path.join(outdir, remname))

	def build_fab(self, fab_dir):
		"""
		Create production Gerber and Excellon files for pcb fabrication
		"""

		self._ensure_dir_exists(fab_dir)
		self.save_readme(os.path.join(fab_dir, 'README.txt'))
		
		for name, layer in self.template['layers'].iteritems():
			self._build_production(fab_dir, layer)

	def build_assembly(self, ass_dir):
		self._ensure_dir_exists(ass_dir) 
		self._build_production(ass_dir, self.template['assembly'])

	def build_production(self, variant, output_dir):
		basename = self._basename()

		fab_dir = os.path.join(output_dir, 'fabrication')
		ass_dir = os.path.join(output_dir, 'assembly')

		#Create fabrication files
		self.build_fab(fab_dir)
		self.zipfab(fab_dir, os.path.join(output_dir, basename + '_fab'))

		#Create assembly files
		self.build_assembly(ass_dir)

		#Create BOM
		bompath = os.path.join(ass_dir, "BOM_%s.xlsx" % basename)
		self.board.export_bom(bompath, variant, format='excel')

	def _basename(self):
		return self.board.part.replace(' ', '_').lower()

	def _ensure_dir_exists(self, output_dir):
		if not os.path.isdir(output_dir):
			os.makedirs(output_dir)

	def _load_template(self, templatefile, template_name):
		"""
		Load a list of possible templates for making gerbers from a json file
		"""

		import json
		with open(templatefile, "r") as f:
			templates = json.load(f)

		if "templates" not in templates:
			raise DataError("Unknown file format for gerber generation template file", path=templatefile, reason="did not contain a 'templates' key")

		options = templates['templates']

		if template_name not in options:
			raise ArgumentError("Unknown template specified for gerber generation", possible_names=options.keys(), name=template_name)

		return options[template_name]

	def zipfab(self, path, output):
		"""
		Create a zipfile of the direction path with the name output.zip that will expand into a directory 
		with the same name as output containing all of the files in path. 
		"""

		zip = zipfile.ZipFile(output+'.zip', 'w', zipfile.ZIP_DEFLATED)
		for root, dirs, files in os.walk(path):
			for file in files:
				zip.write(os.path.join(root, file), os.path.join(os.path.basename(output), file))

		zip.close()
