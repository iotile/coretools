#template.py
#Utilities for producing skeleton code for application modules, unit tests,
#etc. using the Cheetah templating library.

import os.path
import os
from paths import MomoPaths

import Cheetah.Template

class RecursiveTemplate:
	"""
	Either a single Cheetah template document or a 
	directory containing one or more Cheetah template documents.
	In either case, the templates are filled in using supplied
	variables and if name points to a directory under /config/templates
	that directory structure is preserved in the output.
	"""

	def __init__(self, name, rename=None):
		self.objs = []
		self.name = name
		self.recursive = False
		self.rename = rename

		self._build_path()
		self._check_name()
	
	def _build_path(self):
		self.basepath = MomoPaths().templates

	def _check_name(self):
		path = os.path.join(self.basepath, self.name)
		if not os.path.exists(path):
			raise ValueError('%s does not exist' % path)

		if os.path.isdir(path):
			self.recursive = True

	def add(self, obj):
		self.objs.append(obj)

	def clear(self):
		self.objs = []


	def format_string(self, string):
		templ = Cheetah.Template.Template(source=string, searchList=self.objs)

		return str(templ)

	def format_file(self, file_in, file_out):
		templ = Cheetah.Template.Template(file = file_in, searchList=self.objs)

		with open(file_out, "w") as f:
			f.write(str(templ))

	def _ensure_path(self,path):
		if not os.path.exists(path):
			os.makedirs(path)

	def format(self, file_in, output_dir):
		"""
		Given a relative path from the templates directory (file_in), construct
		a file with the same relative path in output_dir by filling in the template
		and filling in file name (if it contains placeholders)
		"""

		inpath = os.path.join(self.basepath, file_in)

		if self.rename is None:
			path = os.path.join(output_dir, file_in)
		else:
			relpath = os.path.relpath(inpath, os.path.join(self.basepath, self.name))
			path = os.path.join(output_dir, self.rename, relpath)

		filled_path = self.format_string(path)
		dname = os.path.dirname(path)

		self._ensure_path(dname)

		self.format_file(inpath, filled_path)

	def render(self, output_dir):
		if not self.recursive:
			self.format(self.name, output_dir)
		else:
			indir = os.path.join(self.basepath, self.name)
			for dirpath, dirs, files in os.walk(indir):
				for f in files:
					inpath = os.path.relpath(os.path.join(dirpath, f), start=self.basepath)
					
					self.format(file_in=inpath, output_dir=output_dir)