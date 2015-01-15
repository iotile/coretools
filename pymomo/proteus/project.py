#project.py
#Create a FIRMWARE project for Proteus VSM 8.0.

import fnmatch
import os
import shutil
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from pymomo.utilities import build, paths

Extensions = ['c', 'asm', 'h', 'inc', 's']

asm_options = []
asm_options.append(['-g'])
asm_options.append(['--debug'])
asm_options.append(['-omf=', 'coff'])
asm_options.append(['-mcpu=', '24F16KA101'])

class Project:
	"""
	Given a directory full of PIC files, create a proteus vsm project. 
	"""

	def __init__(self, dirs, type, template):
		self.dirs = dirs
		self.files = []
		self.template = template

		self.dirs.extend(self._load_shared_dirs(type))

		for d in self.dirs:
			self.files.extend(self._recursive_glob(d, Extensions))

		self._get_name()

	def create(self, out):
		self._make_structure()
		self._copy_files()
		self._copy_template()
		self._build_firmware_xml()
		self._zip_project(out)

	def _file_name(self, f):
		"""
		Given a file name in self.files, return the name that should go in FIRMWARE.XML
		This is the base file name with the project directory prepended.
		"""

		name = os.path.basename(f)

		return "/".join([self.name, name])

	def _add_to_ld(self, ldtag, file, tool):
		new_f = ET.SubElement(ldtag, 'FILE')
		new_f.set('TOOL', tool)

		fname = ET.SubElement(new_f, 'FILE')
		fname.set('NAME', file)

	def _add_option(self, conf_tag, tool, name, value):
		new_o = ET.SubElement(conf_tag, 'OPTION')
		new_o.set('TOOL', tool)
		new_o.set('NAME', name)
		new_o.set('VALUE', value)

	def _configure_asm(self, conf_tag):
		for conf in asm_options:
			if len(conf) == 1:
				conf.append('')

			self._add_option(conf_tag, 'ASM', *conf)

	def _build_firmware_xml(self):
		z = zipfile.ZipFile(self.template, "r")

		with z.open('FIRMWARE/%s.XML' % self.name, "r") as f:
			tree = ET.parse(f)
			root = tree.getroot()

			files = root.find('FILES')

			ld_tags = root.findall(".//FILE[@TOOL='LD']")
			conf_tags = root.findall("./CONFIGURATION")

			#Make sure we add the optimize -O1 flag so that mainboard code
			#compiles (it's too big otherwise)
			for tag in conf_tags:
				self._add_option(tag, 'CC', '', '-O1')
				self._configure_asm(tag)

			#Remove all of the old files from this list
			for elem in files:
				files.remove(elem)

			new_files = [self._file_name(x) for x in self.files]

			#The new version 8.1 of proteus requires the files be listed in the compilation
			#step explicitly, rather than rebuilding it itself if we don't tell it anything.
			for tag in ld_tags:
				for filetag in filter(lambda x: x.tag == 'FILE', tag):
					tag.remove(filetag)

				for f in fnmatch.filter(new_files, '*.c'):
					self._add_to_ld(tag, f, tool='CC')

				for f in fnmatch.filter(new_files, "*.s"):
					self._add_to_ld(tag, f, tool='ASM')

			#Attach Files to the Project for Browsing
			for f in new_files:
				new_f = ET.SubElement(files, 'FILE')
				new_f.set('ATTACH', '1')

				name, ext = os.path.splitext(f)

				if ext == ".h":
					group = 'Header Files'
				else:
					group = "Source Files"

				new_f.set('GROUP', group)
				new_f.set('NAME', f)

			tree.write(os.path.join(self.firm, '%s.XML' % self.name))

	def _get_name(self):
		print "Using Template Project: %s" % os.path.basename(self.template)

		z = zipfile.ZipFile(self.template, "r")
		with z.open('FIRMWARE.XML') as firmfile:
			f = BeautifulSoup(firmfile)

			projs = f.firmware.projects
			names = []

			for p in projs.find_all('string'):
				names.append(p.string.strip())

			if len(names) == 0:
				raise ValueError("Could not extract name from Proteus VSM project")
			elif len(names) > 1:
				raise ValueError("Multiple firmware projects in Proteus VSM project: %s" % str(names))

			print "Found firmware project named: %s" % names[0]

			self.name = names[0] 

	def _copy_template(self):
		"""
		Copy specific files from the template to our version.
		"""

		z = zipfile.ZipFile(self.template, "r")
		z.extract('ROOT.CDB', self.basedir)
		z.extract('ROOT.DSN', self.basedir)
		z.extract('PROJECT.XML', self.basedir)
		z.extract('FIRMWARE.XML', self.basedir)

		#Extract all files in SCRIPTS directory
		for f in z.namelist():
			if "SCRIPTS" in f:
				z.extract(f, self.basedir)


	def _copy_files(self):
		"""
		Copy all of the files into the project directory
		"""

		if not os.path.isdir(self.proj):
			os.makedirs(self.proj)

		for path in self.files:
			shutil.copy2(path, self.proj)

	def _make_structure(self):
		basedir = tempfile.mkdtemp()
		firmdir = os.path.join(basedir, 'FIRMWARE')
		projdir = os.path.join(firmdir, self.name.upper())
		scriptsdir = os.path.join(basedir, 'SCRIPTS')

		os.makedirs(firmdir)
		os.makedirs(projdir)
		os.makedirs(scriptsdir)

		self.basedir = basedir
		self.scripts = scriptsdir
		self.firm = firmdir
		self.proj = projdir

	def _zip_project(self, zipname):
		shutil.make_archive(base_name=zipname, root_dir=self.basedir, base_dir='.', format='zip')

		dirs, filename = os.path.split(zipname)
		shutil.move(zipname + '.zip', os.path.join(dirs, zipname + ".pdsprj"))

	def _load_shared_dirs(self, type):
		"""
		Given the type of project that we're creating (either pic12 or pic24),
		load in the appropriate shared directories.
		"""

		if type not in ["pic12", "pic24"]:
			raise ValueError("Trying to create an unsupported proteus project: type=%s" % type)

		momo = paths.MomoPaths()
		config = build.load_settings()


		port = [os.path.join(momo.base, f) for f in config["reference"]["portable_dirs"]]
		specific = [os.path.join(momo.base, f) for f in config["reference"]["%s_dirs" % type]]

		return port + specific

	def _recursive_glob(self, folder, extensions):
		matches = []

		for root, dirnames, filenames in os.walk(folder):
			for ext in extensions:
				files = fnmatch.filter(filenames, '*.%s' % ext)
				matches.extend([os.path.join(root, f) for f in files])

		return matches