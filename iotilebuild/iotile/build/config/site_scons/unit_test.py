# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#unit_test.py

import os.path
import os
from SCons.Environment import Environment
import test_summary
import fnmatch
from iotile.core.exceptions import *

known_types = {}

class UnitTest (object):
	def __init__(self, files, ignore_extra_attributes=False):
		self.files = files
		self.additional_intermediates = []
		self.extra_modules = []
		self.desc = ''
		self.targets = None
		self.patch = {}
		self.copy_files = []
		self.extra_depends = []

		self.ignore_extra_attributes = ignore_extra_attributes
		self.basedir = os.path.dirname(files[0])

		self._check_files()
		self._extract_header(files[0])
		self._check_files()

		self.status = "Unknown"

	def result_depends(self, filename):
		"""
		Record that the result of this unit test depends on the file filename,
		which is assumed to be located in the unit test's generated folder,
		put there via copy_file, for example.
		"""

		self.extra_depends.append(filename)
	
	def show(self):
		print "#Unit Test#"
		print self.name

		if self.targets is None:
			print "Targets: All module targets"
		else:
			print "Targets:", ", ".join(self.targets)
		print "Status:", self.status
		print self.desc

	def build_dirs(self, chip):
		"""
		Return the appropriate build directories for this unit test.  The build hierarchy is:
		- test: build/test/<CHIP>/<TEST>
		- objects: build/test/<CHIP>/<TEST>/objects
		"""

		basedirs = chip.build_dirs()

		testdir = os.path.join(basedirs['test'], self.name, 'objects')
		outdir = os.path.join(basedirs['test'], self.name)
		finaldir = os.path.join('build', 'test', 'output')
		logdir = os.path.join(finaldir, 'logs')

		return {'test':outdir, 'objects': testdir, 'logs': logdir}

	def get_path(self, obj, chip):
		"""
		Get the canonical path for various build products of the unit test.  Currently understands:
		- rawlog: the raw output from the simulator run
		- log: the processed version of rawlog into a standard format
		"""

		dirs = self.build_dirs(chip)

		if obj == 'rawlog':
			name = self.name + '@' + chip.arch_name() + '.raw'
			return os.path.join(dirs['objects'], name)
		elif obj == 'log':
			name = self.name + '@' + chip.arch_name() + '.log'
			return os.path.join(dirs['logs'], name)
		elif obj == 'status':
			name = self.name + '@' + chip.arch_name() + '.status'
			return os.path.join(dirs['logs'], name)
		elif obj == 'elf':
			name = self.name + '.elf'
			return os.path.join(dirs['objects'], name)
		else:
			raise BuildError("Path to unknown build product asked for", unit_test=self.name, object=obj, arch=chip.name)

	def build_target(self, target, summary_env):
		raise BuildError('The build_target method must be overriden by a UnitTest subclass', unit_test=self.name, type=str(self.__class__))

	def check_output(self, chip, log):
		"""
		If unit tests have additional things to check about the unit test's output,
		they should override this function and return False if the test fails these
		additional checks. They may also choose to open log for appending and log the
		reason for this failure. 
		"""

		return True

	def save_status(self, path, passed):
		with open(path, "w") as f:
			if passed :
				f.write('PASSED')
			else:
				f.write('FAILED')

	def build(self, module_targets, summary_env):
		"""
		Build this unit test for the intersection of the targets that it is designed for
		and the targets that the module it is targeted at is designed for.  If more architectures
		are specified in the module_targets than in a unit test, the unit test is assumed to
		apply if all of the architectures in the unit test are contained in the module_target.
		"""

		for mod_target in module_targets:
			found = False
			if self.targets is not None:
				for target in self.targets:
					target_archs = set(target.split('/'))
					if target_archs <= mod_target.archs():
						found = True
						break

				if found is False:
					continue

			self.build_target(mod_target, summary_env)

	def _check_files(self):
		"""
		All files should be c or assembly files (.c or .as) and should
		exist.
		"""

		for file in self.files:
			valid = set (['.c', '.as', '.asm'])
			ext = os.path.splitext(file)[1]

			if not os.path.exists(file):
				raise BuildError('Test source file does not exist', file=file)
			if ext not in valid:
				raise BuildError('Test source file does not has .c,.as or .asm extension', file=os.path.basename(file))

		return True

	def _parse_targets(self, targets):
		"""
		Parse the targets specified for this unit test into canonical format
		allowing subclasses to handle targets specified for them by overriding
		the _parse_target(self, target) method to return the canonical name
		for the target
		"""

		if targets.lower() == 'all':
			self.targets = None
			return

		targets = targets.split(',')

		canonical_targets = []

		for target in targets:
			t = target.strip()
			canonical_targets.append(self._parse_target(t))

		self.targets = canonical_targets

	def copy_file(self, src_file, dst_name):
		"""
		Copy a specified file into the unit test object directory

		Subclasses can use this routine to add files that are necessary
		for the unit test to run.  It is up to each unit test subclass
		to implement the actual copying in whatever way is appropriate,
		this call just sets that a file should be copied.
		"""

		self.copy_files.append((src_file, dst_name))

	def find_support_file(self, support_name, target):
		"""
		Given the name of a support file, try to find it by looking in the 
		same directory as the first unit test file and searching the following
		names, where target is a list of architectures like:
		arch1/arch2/arch3
		
		name_arch1_arch2_arch3.ext
		name_arch1_arch2.ext
		name_arch1.ext
		name.ext

		If no file can be found, return None.
		"""

		name, ext = os.path.splitext(support_name)

		prefixes = list(reversed(target.arch_prefixes()))
		prefixes.append([])
		for prefix in prefixes:
			name_str = "_".join([name] + prefix)
			name_str += ext

			if os.path.exists(name_str):
				return name_str

		raise BuildError("could not find support file", filename=support_name, arch_prefixes=prefixes)

	def _extract_header(self, file):
		"""
		Process the first commented block in the file and extract the assignments
		from it, parsing out the name, targets, and description
		"""

		header = []
		with open(file, "r") as f:
			for line in f:
				line = line.strip()

				#ignore blank lines
				if line == '':
					continue

				if line[0] == ';':
					header.append(line[1:])
				elif line[0:2] == '//':
					header.append(line[2:])
				else:
					break

		for line in header:
			v = line.split(':')

			#Undelimited lines after the description are assumed
			#to be continuations of the description
			if len(v) < 2:
				if hasattr(self, 'desc'):
					self.desc += v[0]
			elif len(v) == 2:
				name = v[0]
				val = v[1]
				name = name.strip()
				val = val.strip()

				name = name.lower()
				
				#Check if we support this attribute natives
				if name == 'name':
					self.name = val
				elif name == 'type':
					self.type = val
				elif name == 'description':
					self.desc = val
				else:
					#All other attributes are parsed by handlers that either
					#we or a subclass provide, so check if the attribute has
					#a handler or fail

					name = name.replace(' ', '_') #make sure this is a valid python identifier name

					handlern = '_parse_%s' % name
					if hasattr(self, handlern):
						handler = getattr(self, handlern)
						handler(val)
					elif not self.ignore_extra_attributes: 
						raise BuildError("Unknown attribute encountered with no handler", file=file, attribute=name, value=val, type=str(self.__class__))

		#Make sure that all of the right information has been found
		required_attributes = ['name', 'type']
		for attr in required_attributes:
			if not hasattr(self, attr):
				raise BuildError("test does not have a complete header", file=file, missing_attribute=attr)

	def _parse_target(self, value):
		return value

	def _parse_patches(self, value):
		"""
		Parse a list of symbols that need to be patched in the test. Each specific architecture
		can choose to do what it wants with this list.
		"""

		parsed = value.split(',')
		pairs = [x.rstrip().lstrip().split('->') for x in parsed]
		mapper = {name: value for name,value in pairs}
		self.patch = mapper

	def add_intermediate(self, file, folder=None):
		"""
		Add a file to the list of intermediate build products produced by this unit test.
		This is important for letting SCons know about the file so that it can clean it up
		properly.  If folder is specified, is should be one of the values returned by
		build_dirs() and it will be replaced with the appropriate build directory for the
		target being built.
		"""

		self.additional_intermediates.append((folder, file))

	def get_intermediates(self, chip):
		dirs = self.build_dirs(chip)

		paths = []

		for folder, p in self.additional_intermediates:
			if folder is None:
				paths.append(p)
			 	continue

			basepath = dirs[folder]
			paths.append(os.path.join(basepath, p))

		return paths

def find_units(parent):
	files = [f for f in os.listdir(parent) if os.path.isfile(os.path.join(parent, f))]

	#ignore hidden files
	files = filter(lambda x: x[0] != '.', files)

	#only look for files that start with test_
	files = filter(lambda x: x.startswith("test_"), files)

	files = [os.path.join(parent, f) for f in files]

	tests = []

	for f in files:
		unit = UnitTest([f], ignore_extra_attributes=True)
		
		if unit.type not in known_types:
			raise BuildError("Unknown test type in unit test", name=unit.name, type=unit.type)

		test = known_types[unit.type]([f])
		tests.append(test)

	return tests

def find_sources(src_dir, patterns=('*.c', '*.as', '*.asm')):
	"""
	Given a source directory, recursively find all source and header files under that directory
	"""

	include_dirs = set()
	src = {}
	headers = {}

	for root, dirnames, filenames in os.walk(src_dir):
		dir_headers = fnmatch.filter(filenames, '*.h')
		if len(dir_headers) > 0:
			include_dirs.add(root)

		headers.update({os.path.splitext(x)[0]: os.path.join(root, x) for x in dir_headers})

		for s in patterns:
			dir_srcs = fnmatch.filter(filenames, s)
			src.update({os.path.splitext(x)[0]: os.path.join(root, x) for x in dir_srcs})

	return include_dirs, src, headers


def build_units(parent, targets):
	tests = find_units(parent)

	summary_env = Environment(tools=[])
	summary_env['TESTS'] = []

	for test in tests:
		test.build(targets, summary_env)

	build_summary(summary_env)

def build_summary_name():
	return os.path.join('build', 'test', 'output', 'results.txt')

def build_summary(env):
	summary = env.Command([build_summary_name()], env['TESTS'], action=env.Action(test_summary.build_summary_cmd, "Creating test summary"))
	env.AlwaysBuild(summary)
