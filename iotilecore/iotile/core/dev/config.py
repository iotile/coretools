"""Manager for typed configuration variables

ConfigManager allows plugins to register typed config variables
and allows users to then set those variables.  Config variables
can optionally have default values.  Plugins to iotile-core can
register their own config variables under their own namespace
by registering an entry_point named 'iotile.config_variables'.

The object pointed to by the entry point should be a function that
returns a 2-tuple with a string and a list that maps a namespace prefix
to a list of 4-tuples with format:

[name, type, description, default_value]

If there is no default value, a 3-tuple can be used with just name, type
and description.

"""
import pkg_resources
import fnmatch
from collections import namedtuple
from iotile.core.dev.registry import ComponentRegistry
from iotile.core.exceptions import ArgumentError, ValidationError, EnvironmentError
from iotile.core.utilities.typedargs import context, param, return_type, stringable, type_system

MISSING = object()
ConfigVariable = namedtuple("ConfigVariable", ['name', 'type', 'description', 'default'])

@context("ConfigManager")
class ConfigManager(object):
    """A class for managing typed configuration variables

    ConfigManager can be used to querying which config variables are defined
    and to set or get the currently defined variables.
    """

    def __init__(self):
        self._known_variables = {}
        self._load_providers()
        self._reg = ComponentRegistry()

    def _load_providers(self):
        """Load all config_variables providers using pkg_resources
        """

        for entry in pkg_resources.iter_entry_points('iotile.config_variables'):
            try:
                provider = entry.load()
                prefix, conf_vars = provider()
            except (ValueError, TypeError) as exc:
                raise EnvironmentError("Error loading config variables", package=entry.name, error=str(exc))

            for var in conf_vars:
                if len(var) != 3 and len(var) != 4:
                    raise EnvironmentError("Error loading config variable, invalid length", data=var, package=entry.name)

                name = prefix + ':' + var[0]
                if len(var) == 3:
                    var_obj = ConfigVariable(var[0], var[1], var[2], MISSING)
                else:
                    var_obj = ConfigVariable(name, var[1], var[2], var[3])

                if name in self._known_variables:
                    raise EnvironmentError("The same config variable was defined twice", name=name)

                self._known_variables[name] = var_obj

    def _format_variable(self, var):
        """Format a helpful string describing a config variable

        Args:
            var (ConfigVariable): the variable to format

        Returns:
            string: The formatted string in the form name (type): (default %s) description
        """

        if var.default is MISSING:
            return "%s (%s): %s [no default]" % (var.name, var.type, var.description)

        return "%s (%s): %s [default: %s]" % (var.name, var.type, var.description, var.default)

    @param("glob", "string", desc="Glob pattern for finding config variables")
    @return_type("list(string)")
    def list(self, glob):
        """List all matching config variables

        The glob parameter should be a wildcard expression like:
        build:* to find all config variables defined with a build prefix.

        Returns:
            string[]: A list of string descriptions containing descriptions and
                type information.
        """

        known_vars = [x for x in sorted(self._known_variables.iterkeys()) if fnmatch.fnmatchcase(x, glob)]
        return ['- ' + self._format_variable(self._known_variables[x]) for x in known_vars]

    @param("name", "string", desc="Config variable to find")
    @stringable
    def get(self, name):
        """Get the current value of a config variable
        """

        if name not in self._known_variables:
            raise ArgumentError("Unknown config variable", name=name)

        var = self._known_variables[name]

        try:
            val = self._reg.get_config(name)
        except ArgumentError:
            if var.default is not MISSING:
                val = var.default
            else:
                raise ArgumentError("Config variable not set and there is no default value", name=name)

        typed_val = type_system.convert_to_type(val, var.type)
        return typed_val

    @param("name", "string", desc="Config variable to find")
    @stringable
    def remove(self, name):
        """Remove any currently defined values for the named variable
        """

        self._reg.clear_config(name)

    @param("name", "string", desc="Config variable to set")
    @param("value", "string", desc="Value to set")
    def set(self, name, value):
        """Set the current avlue of a config variable
        """

        if name not in self._known_variables:
            raise ArgumentError("Unknown config variable", name=name)

        self._reg.set_config(name, value)

    @param("name", "string", desc="Config variable to find")
    @return_type("string")
    def describe(self, name):
        """Describe a config variable by name

        Returns:
            string: A short description of what the variable is used for
        """

        if name not in self._known_variables:
            raise ArgumentError("Unknown config variable", name=name)

        var = self._known_variables[name]
        return self._format_variable(var)

    def add_variable(self, name, var_type, desc, default=MISSING):
        """Add a temporary variable to the config variable manager

        This function is mainly useful for testing since it does not
        persistently store information about the variable.

        Args:
            name (string): The name of the variable
            var_type (string): The type of the variable.  This should be a type
                known to the type_system.
            desc (string): The description of what this variable is for
            default (string): An optional default value for the variable 
        """

        self._known_variables[name] = ConfigVariable(name, var_type, desc, default)
