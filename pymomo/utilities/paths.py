
import os.path
import sys
import subprocess
import functools
import platform
import os

from pkg_resources import resource_filename, Requirement

class MissingConfigError(Exception):
  """A required configuration environment variable was not found."""
  def __init__(self, var):
    self.msg = "A required configuration environment variable (%s) was not found" % var
  def __str__(self):
  	return self.msg

class MomoPaths:
	def __init__(self):
		self.config = resource_filename(Requirement.parse("pymomo"), "pymomo/config")
		self.base = os.environ.get('MOMOPATH')

		if self.base == None:
			raise MissingConfigError('MOMOPATH')

		self.modules = os.path.join(self.base, 'momo_modules')
		self.templates = os.path.join(self.config, 'templates')
		self.pcb = os.path.join(self.base, 'pcb')
		self.site_tools = os.path.join(self.config, 'site_scons')
		self.settings = self._find_settings_dir()

	def _find_settings_dir(self):
		"""
		Find a per user settings directory that is appropriate for each
		type of system that we are installed on.
		"""

		system = platform.system()

		basedir = None

		if system == 'Windows':
			if 'APPDATA' in os.environ:
				basedir = os.environ['APPDATA']
		elif system == 'Darwin':
			basedir = os.path.expanduser('~/Library/Preferences')

		#If we're not on Windows or Mac OS X, assume we're on some
		#kind of posix system where the appropriate place would be
		#~/.config
		if basedir is None:
			basedir = os.path.expanduser('~')
			basedir = os.path.join(basedir, '.config')

		settings_dir = os.path.abspath(os.path.join(basedir, 'WellDone-MoMo'))
		if not os.path.exists(settings_dir):
			os.makedirs(settings_dir, 0755)

		return settings_dir

	def select(self, *args, **kwargs):
		"""
		Given a base path, return a list of all of the files under that path that match the given filter.
		*args should be a list of path components that are joined together using path.join to form the base
		search path

		**kwargs takes the following options:
		- filter: 	a function that is applied to the file paths found using this function to select only a subset
					filter is passed 3 arguments, (the absolute file path, the file name, its extension)
		- recursive: a boolean.  If True or not specified, search under all subdirectories as well
		- dirs: a boolean.  If True, only search directory names, if False or unspecified, search only file names
		"""

		base = os.path.join(*args)
		files = []

		for (dirpath, dirnames, filenames) in os.walk(base):
			if 'dirs' in kwargs and kwargs['dirs'] == True:
				entries = dirnames
			else:
				entries = filenames

			full_paths = map(lambda x: os.path.join(base, dirpath, x), entries)


			if "filter" not in kwargs:
				files.extend(full_paths)
			else:
				split_names = map(lambda x: os.path.splitext(x), entries)
				wanted_files = [full_paths[i] for i in xrange(0, len(entries)) if kwargs['filter'](full_paths[i], split_names[i][0], split_names[i][1]) == True]

				files.extend(wanted_files)

			if 'recursive' in kwargs and kwargs['recursive'] == False:
				break

		return files

def memoize(obj):
	cache = obj.cache = {}

	@functools.wraps(obj)
	def memoizer(*args, **kwargs):
		key = str(args) + str(kwargs)
		if key not in cache:
			cache[key] = obj(*args, **kwargs)
		return cache[key]
	
	return memoizer

@memoize
def convert_path(path):
	"""
	If we are running on cygwin and passing an absolute path to a utility that is not cygwin
	aware, we need to convert that path to a windows style path. 
	"""

	if not os.path.isabs(path):
		return '"' + path + '"'

	if sys.platform == 'cygwin':
		out = subprocess.check_output(['cygpath', '-mw', path])
		out = out.lstrip().rstrip()
		return '"' + out + '"'

	return '"' + path + '"'
