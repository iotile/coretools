# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

from pkg_resources import resource_filename, Requirement
from typedargs.exceptions import ArgumentError
from iotile.build.utilities import render_template


KNOWN_HARDWARE_TYPES = {
    10: "NXP LPC824 (Cortex M0+)"
}


class TBBlock(object):
    """
    The block in program memory describing a MoMo application module.  The MIB block
    contains information on the application module and a sparse matrix representation
    of a jump table containing all of the command ids and interfaces that the module
    knows how to respond to.
    """

    CommandFileTemplate = 'command_map_c.c.tpl'
    CommandHeaderTemplate = 'command_map_c.h.tpl'
    ConfigFileTemplate = 'config_variables_c.c.tpl'
    ConfigHeaderTemplate = 'config_variables_c.h.tpl'

    def __init__(self):
        """
        Given an intelhex object, extract the MIB block information
        from it or raise an exception if a TBBlock cannot be found
        at the right location.
        """

        self.commands = {}
        self.configs = {}
        self.api_version = None
        self.name = None
        self.module_version = None
        self.hw_type = -1

        self._parse_hwtype()

    def to_dict(self):
        """Convert this object into a dictionary.

        Returns:
            dict: A dict with the same information as this object.
        """

        out_dict = {}

        out_dict['commands'] = self.commands
        out_dict['configs'] = self.configs
        out_dict['short_name'] = self.name
        out_dict['versions'] = {
            'module': self.module_version,
            'api': self.api_version
        }

        return out_dict

    @classmethod
    def _is_byte(cls, val):
        return val >= 0 and val <= 255

    def set_api_version(self, major, minor):
        """
        Set the API version this module was designed for.

        Each module must declare the mib12 API version it was compiled with as a
        2 byte major.minor number.  This information is used by the pic12_executive
        to decide whether the application is compatible.
        """

        if not self._is_byte(major) or not self._is_byte(minor):
            raise ArgumentError("Invalid API version number with component that does not fit in 1 byte", major=major, minor=minor)

        self.api_version = (major, minor)

    def set_module_version(self, major, minor, patch):
        """
        Set the module version for this module.

        Each module must declare a semantic version number in the form:
        major.minor.patch

        where each component is a 1 byte number between 0 and 255.
        """

        if not (self._is_byte(major) and self._is_byte(minor) and self._is_byte(patch)):
            raise ArgumentError("Invalid module version number with component that does not fit in 1 byte", major=major, minor=minor, patch=patch)

        self.module_version = (major, minor, patch)

    def set_name(self, name):
        """
        Set the module name to a 6 byte string

        If the string is too short it is appended with space characters.
        """

        if len(name) > 6:
            raise ArgumentError("Name must be at most 6 characters long", name=name)

        if len(name) < 6:
            name += ' '*(6 - len(name))

        self.name = name

    def add_command(self, cmd_id, handler):
        """
        Add a command to the TBBlock.

        The cmd_id must be a non-negative 2 byte number.
        handler should be the command handler
        """

        if cmd_id < 0 or cmd_id >= 2**16:
            raise ArgumentError("Command ID in mib block is not a non-negative 2-byte number", cmd_id=cmd_id, handler=handler)

        if cmd_id in self.commands:
            raise ArgumentError("Attempted to add the same command ID twice.", cmd_id=cmd_id, existing_handler=self.commands[cmd_id],
                                new_handler=handler)

        self.commands[cmd_id] = handler

    def add_config(self, config_id, config_data):
        """
        Add a configuration variable to the MIB block
        """

        if config_id < 0 or config_id >= 2**16:
            raise ArgumentError("Config ID in mib block is not a non-negative 2-byte number", config_data=config_id, data=config_data)

        if config_id in self.configs:
            raise ArgumentError("Attempted to add the same command ID twice.", config_data=config_id, old_data=self.configs[config_id],
                                new_data=config_data)

        self.configs[config_id] = config_data

    def _parse_hwtype(self):
        """Convert the numerical hardware id to a chip name."""

        self.chip_name = KNOWN_HARDWARE_TYPES.get(self.hw_type, "Unknown Chip (type=%d)" % self.hw_type)

    def render_template(self, template_name, out_path=None):
        """Render a template based on this TileBus Block.

        The template has access to all of the attributes of this block as a
        dictionary (the result of calling self.to_dict()).

        You can optionally render to a file by passing out_path.

        Args:
            template_name (str): The name of the template to load.  This must
                be a file in config/templates inside this package
            out_path (str): An optional path of where to save the output
                file, otherwise it is just returned as a string.

        Returns:
            string: The rendered template data.
        """

        return render_template(template_name, self.to_dict(), out_path=out_path)
