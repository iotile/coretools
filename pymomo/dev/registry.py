from pymomo.utilities.typedargs.annotate import *
from pymomo.utilities import typedargs
from pymomo.utilities.kvstore import KeyValueStore
from pymomo.exceptions import *
import json
import os.path
from iotile import IOTile

@context()
class ComponentRegistry:
	"""
	ComponentRegistry

	A mapping of all of the installed components on this system that can
	be used as build dependencies and where they are located.
	"""

	def __init__(self):
		self.kvstore = KeyValueStore('component_registry.db')

	@param("component", "path", "exists", desc="Path to the componnent directory")
	def add(self, component):
		"""
		Register a component with ComponentRegistry. 

		Component must be a buildable object with a module_settings.json file that
		describes its name and the domain that it is part of.
		"""

		tile = IOTile(component)
		value = os.path.normpath(os.path.abspath(component))

		self.kvstore.set(tile.name, value)

	@param("key", "string", desc="Name of registered component to find")
	@param("domain", "string")
	def find(self, key, domain=""):
		try:
			if domain is not "":
				key = domain.lower() + '/' + key

			return IOTile(self.kvstore.get(key))
		except KeyError:
			raise ArgumentError("Unknown component name", name=key)

	@param("key", "string", desc="Name of registered component to remove")
	@return_type('string')
	def remove(self, key):
		"""
		Remove component from registry
		"""

		return self.kvstore.remove(key)

	@annotated
	def clear(self):
		"""
		Clear all of the registered components
		"""

		self.kvstore.clear()
