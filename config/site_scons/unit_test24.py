from unit_test import UnitTest, find_sources
import pic24
import os
import sys
import unit_test

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from pymomo.exceptions import *
from pymomo.utilities import paths

class Pic24ModuleTest (UnitTest):
	"""
	A unit test for the PIC24 series of microprocessors that tests a single .c/.h module
	providing mocks for any other modules that the module under test (MUT) references.
	"""

	def __init__(self, files, **kwargs):
		self.includes = []
		self.additional_sources = []

		UnitTest.__init__(self, files, **kwargs)

		self.processed_dirs = set()

		modname = self._build_module_name(files[0])
		self._find_module(modname)
		for name in self.extra_modules:
			self._find_module(name)
		
	def _build_module_name(self, testfile):
		testfile = os.path.basename(self.files[0])
		if not testfile.startswith('test_'):
			raise InternalError('Module unit test does not have an appropriate filename: %s' % testfile)

		modname = os.path.splitext(testfile)[0][5:]
		return modname
	
	def _find_module(self, modname):
		if self._find_in_dir(modname) == False:
			found = False
			for src in self.additional_sources:
				found = self._find_in_dir(modname, src)
				if found:
					break

			if not found:
				raise InternalError("Could not find module %s for module unit test %s" % (modname, self.name))

	def _find_in_dir(self, modname, srcdir=None):
		if srcdir is None:
			testdir = os.path.dirname(self.files[0])
			srcdir = os.path.abspath(os.path.join(testdir, '..', 'src'))

		incdirs, sources, headers = find_sources(srcdir)
		normsrc = os.path.normpath(srcdir)

		if normsrc not in self.processed_dirs:
			self.includes += incdirs
			self.processed_dirs.add(normsrc)

		if modname not in sources:
			return False

		self.files.append(sources[modname])
		return True

	def _parse_target(self, target):
		return target

	def _parse_sources(self, value):
		"""
		Parse an additional source directory other than simply src
		"""

		basedir = os.path.dirname(self.files[0])
		srcpath = os.path.normpath(os.path.join(basedir, value))
		self.additional_sources.append(srcpath)

	def _parse_modules(self, value):
		"""
		For module unit tests where the test just compiles one or several modules, allow
		the user to specify extra modules that need to be compiled in.
		"""

		parsed = value.split(',')
		files = map(lambda x: x.rstrip().lstrip(), parsed)
		self.extra_modules = files

	def build_target(self, target, summary_env):
		statusnode = pic24.build_moduletest(self, target)
		summary_env['TESTS'].append(statusnode)
			
unit_test.known_types['module'] = Pic24ModuleTest