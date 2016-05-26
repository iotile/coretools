# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from iotilecore.utilities.kvstore import KeyValueStore
from iotilecore.exceptions import *
import json
import os.path
from iotileobj import IOTile

class ComponentRegistry:
	"""
	ComponentRegistry

	A mapping of all of the installed components on this system that can
	be used as build dependencies and where they are located.  Also used
	to manage iotile plugins.
	"""

	def __init__(self):
		self.kvstore = KeyValueStore('component_registry.db')
		self.plugins = KeyValueStore('iotile_plugins.db')

	def add_component(self, component):
		"""
		Register a component with ComponentRegistry. 

		Component must be a buildable object with a module_settings.json file that
		describes its name and the domain that it is part of.
		"""

		tile = IOTile(component)
		value = os.path.normpath(os.path.abspath(component))

		self.kvstore.set(tile.name, value)

	def add_plugin(self, name, package):
		"""
		Register a plugin into the iotile tool to add additional functionality.
		"""

		self.plugins.set(name, package)

	def remove_plugin(self, name):
		"""
		Remove a plugin from the iotile based on its name.
		"""

		self.plugins.remove(name)

	def list_plugins(self):
		"""
		List all of the plugins that have been registerd for the iotile program on this computer
		"""

		vals = self.plugins.get_all()

		return {x: y for x,y in vals}

	def find_component(self, key, domain=""):
		try:
			if domain is not "":
				key = domain.lower() + '/' + key.lower()

			return IOTile(self.kvstore.get(key))
		except KeyError:
			raise ArgumentError("Unknown component name", name=key)

	def remove_component(self, key):
		"""
		Remove component from registry
		"""

		return self.kvstore.remove(key)

	def clear_components(self):
		"""
		Clear all of the registered components
		"""

		self.kvstore.clear()

	def list_components(self):
		"""
		List all of the registered component names
		"""

		items = self.kvstore.get_all()

		return [x[0] for x in items]