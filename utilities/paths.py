
import os.path
import sys
import subprocess
import functools

class MomoPaths:
	def __init__(self):
		self.base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..' ))

		self.config = os.path.join(self.base, 'config')
		self.modules = os.path.join(self.base, 'momo_modules')
		self.templates = os.path.join(self.config, 'templates')
		self.pcb = os.path.join(self.base, 'pcb')
		self.resources = os.path.join(self.base, 'resources')

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
		return path

	if sys.platform == 'cygwin':
		out = subprocess.check_output(['cygpath', '-mw', path])
		out = out.lstrip().rstrip()
		return out

	return path
