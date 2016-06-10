# Annotated Registry
# A wrapper to make the IOTile component registry accessible in the iotile
# tool.  Since the registry is used internally in the type system it cannot 
# itself make use of typedargs annotations
from iotilecore.utilities.typedargs import annotated, param, return_type, context, iprint

_name_ = "Developer"

#Outside accessible API for this package
from registry import ComponentRegistry

@annotated
def registry():
	return AnnotatedRegistry()

@context()
class AnnotatedRegistry:
	"""
	AnnotatedRegistry

	A mapping of all of the installed components on this system that can
	be used as build dependencies and where they are located.  Also used
	to manage iotile plugins.
	"""

	def __init__(self):
		self.reg = ComponentRegistry()

	@param("component", "path", "exists", desc="folder containing component to register")
	def add_component(self, component):
		"""
		Register a component with ComponentRegistry. 

		Component must be a buildable object with a module_settings.json file that
		describes its name and the domain that it is part of.
		"""

		self.reg.add_component(component)

	@param("name", "string", desc="iotile context name to add")
	@param("package", "string", desc="python package and function/object to call")
	def add_plugin(self, name, package):
		"""
		Register a plugin into the iotile tool to add additional functionality.
		"""

		self.reg.add_plugin(name, package)

	@param("name", "string", desc="iotile context name to remove")
	def remove_plugin(self, name):
		"""
		Remove a plugin from the iotile based on its name.
		"""

		self.reg.remove_plugin(name)

	@return_type("map(string, string)")
	def list_plugins(self):
		"""
		List all of the plugins that have been registerd for the iotile program on this computer
		"""

		return self.reg.list_plugins()

	def find_component(self, key, domain=""):
		return self.reg.find_component(key, domain)

	@param("key", "string", desc="iotile component to find")
	def remove_component(self, key):
		"""
		Remove component from registry
		"""

		return self.reg.remove_component(key)

	@annotated
	def clear_components(self):
		"""
		Clear all of the registered components
		"""

		self.reg.clear_components()

	@return_type("list(string)")
	def list_components(self):
		"""
		List all of the registered component names
		"""

		return self.reg.list_components()

	@return_type("map(string, string)")
	def check_components(self):
		"""
		Checks to see if all registered components are up-to-date git repositories
		"""

		return self.reg.check_components()
