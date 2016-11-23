from iotile.core.utilities.typedargs import context, annotated, param, return_type, iprint
from iotile.core.dev.iotileobj import IOTile
from iotile.core.exceptions import *
from resolverchain import DependencyResolverChain
import os

@context("DependencyManager")
class DependencyManager (object):
	"""Tools to manage IOTile dependencies and build infrastructure.

	"""

	def __init__(self):
		pass

	@param("path", "path", "exists", desc="Path to IOTile to check")
	@return_type('basic_dict')
	def info(self, path="."):
		"""Get information on an IOTile component.
		
		If path is not given, the current directory is assumed to be an IOTile component.
		"""

		tile = IOTile(path)

		info = {
			'is_development_version': not tile.release,
			'dependencies': tile.dependencies
		}

		return info

	@return_type('map(string, string)')
	@param("path", "path", "exists", desc="Path to IOTile to check")
	def list(self, path='.'):
		"""Check if all necessary dependencies of this tile are satisfied

		Returns
		=======
	
		A map with a string value for each dependency where the value is one of:
		- 'not installed' when there is no dependency currently in build/deps
		- 'installed' when the dependency in build/deps is valid
		- 'invalid version' when the dependency in build/deps has an invalid version
		"""

		tile = IOTile(path)

		if tile.release:
			raise ArgumentError("Cannot check dependencies on a release mode tile that cannot have dependencies")

		dep_stati = {}

		for dep in tile.dependencies:
			try:
				deptile = IOTile(os.path.join(path, 'build', 'deps', dep['unique_id']))
			except EnvironmentError, IOError:
				dep_stati[dep['name']] = 'not installed'
				continue

			dep_stati[dep['name']] = 'installed'

			#TODO: Check if the dependencies have the correct version

		return dep_stati

	@return_type('map(string, string)')
	@param("path", "path", "exists", desc="Path to IOTile to check")
	def versions(self, path='.'):
		"""Return the version of all installed dependencies

		Returns
		=======
	
		A map with a string value for each dependency where the value is one of:
		- 'not installed' when there is no dependency currently in build/deps
		- 'X.Y.Z' with the version of the dependency when it is installed
		"""

		tile = IOTile(path)

		if tile.release:
			raise ArgumentError("Cannot check dependencies on a release mode tile that cannot have dependencies")

		dep_stati = {}

		for dep in tile.dependencies:
			try:
				deptile = IOTile(os.path.join(path, 'build', 'deps', dep['unique_id']))
			except EnvironmentError, IOError:
				dep_stati[dep['name']] = 'not installed'
				continue

			dep_stati[dep['name']] = str(deptile.version)

			#TODO: Check if the dependencies have the correct version

		return dep_stati

	@param("path", "path", "exists", desc="Path to IOTile to check")
	def update(self, path='.'):
		"""Attempt to resolve all dependencies in this IOTile by installing them into build/deps
		"""

		tile = IOTile(path)
		if tile.release:
			raise ArgumentError("Cannot update dependencies on a release mode tile that cannot have dependencies")

		depdir = os.path.join(tile.folder, 'build', 'deps')

		#FIXME: Read resolver_settings.json file
		resolver_chain = DependencyResolverChain()
		
		for dep in tile.dependencies:
			result = resolver_chain.update_dependency(tile, dep)
			iprint("Resolving %s: %s" % (dep['name'], result))

	@param("path", "path", "exists", desc="Path to IOTile to check")
	def clean(self, path='.'):
		"""Remove all dependencies of this IOTile from build/deps
		"""

		tile = IOTile(path)
		if tile.release:
			raise ArgumentError("Cannot update dependencies on a release mode tile that cannot have dependencies")

		depdir = os.path.join(tile.folder, 'build', 'deps')

		import shutil
		shutil.rmtree(depdir)
		os.makedirs(depdir)
