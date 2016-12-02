# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#descriptor.py
#Define a Domain Specific Language for specifying MIB endpoints

from pyparsing import Word, Regex, nums, hexnums, Literal, Optional, Group, oneOf, QuotedString
from handler import TBHandler
import sys
import os.path
from iotile.core.exceptions import *
import block
import shutil
from pkg_resources import resource_filename, Requirement
from iotile.build.utilities.template import RecursiveTemplate
import struct

#DSL for mib definitions
#Format:
#feature <i>
#[j:] _symbol(n [ints], yes|no)
#[j+1:] _symbol2(n [ints], yes|no)
#The file should contain a list of statements beginning with a feature definition
#and followed by 1 or more command definitions.  There may be up to 128 feature definitions
#each or which may have up to 128 command definitions.  Whitespace is ignored.  Lines starting
#with # are considered comments and ignored.
symbol = Regex('[_a-zA-Z][_a-zA-Z0-9]*')
filename = Regex('[_a-zA-Z][_a-zA-Z0-9]*\.mib')
strval = Regex('"[_a-zA-Z0-9. ]+"')
number = Regex('((0x[a-fA-F0-9]+)|[0-9]+)').setParseAction(lambda s,l,t: [int(t[0], 0)]) | symbol
ints = number('num_ints') + Optional(Literal('ints') | Literal('int'))
has_buffer = (Literal('yes') | Literal('no')).setParseAction(lambda s,l,t: [t[0] == 'yes'])
comma = Literal(',').suppress()
quote = Literal('"').suppress()

left = Literal('(').suppress()
right = Literal(')').suppress()
colon = Literal(':').suppress()
leftB = Literal('[').suppress()
rightB = Literal(']').suppress()
comment = Literal('#')

valid_type = oneOf('uint8_t uint16_t uint32_t int8_t int16_t int32_t char')

assignment_def = symbol("variable") + "=" + (number('value') | strval('value')) + ';'
cmd_def = number("cmd_number") + colon + symbol("symbol") + left + ints + comma + has_buffer('has_buffer') + right + ";"
include = Literal("#include") + quote + filename("filename") + quote
interface_def = Literal('interface') + number('interface') + ';'

reqconfig = number("confignum") + colon + Literal('required').suppress() + Literal('config').suppress() + valid_type('type') + symbol('configvar') + Optional(leftB + number('length') + rightB) + ';'
optconfig = number("confignum") + colon + Literal('optional').suppress() + Literal('config').suppress() + valid_type('type') + symbol('configvar') + Optional(leftB + number('length') + rightB) + "=" + (number('value') | QuotedString(quoteChar='"', unquoteResults=False)('value')) + ';'

statement = include | cmd_def | comment | assignment_def | interface_def | reqconfig | optconfig

#Known Variable Type Lengths
type_lengths = {'uint8_t': 1, 'char': 1, 'int8_t': 1, 'uint16_t': 2, 'int16_t':2, 'uint32_t': 4, 'int32_t': 4} 
type_codes = {'uint8_t': 'B', 'char': 'B', 'int8_t': 'b', 'uint16_t': 'H', 'int16_t': 'h', 'uint32_t': 'L', 'int32_t': 'l'} 

class TBDescriptor:
    """
    Class that parses a .mib file which contains a DSL specifying the valid MIB endpoints
    in a MIB12 module and can output an asm file containing the proper MIB command map
    for that architecture.
    """

    def __init__(self, source, include_dirs=[]):
        self.variables = {}
        self.commands = {}
        self.interfaces = []
        self.configs = {}
        self.valid = False

        self.include_dirs = include_dirs + [resource_filename(Requirement.parse("iotile-build"), "iotile/build/config")]

        if isinstance(source, basestring):
            source = [source]

        for filename in source:
            self._parse_file(filename)

    def _parse_file(self, filename):
        with open(filename, "r") as f:
            for l in f:
                line = l.lstrip().rstrip()

                if line == "":
                    continue

                self._parse_line(line)

    def generate_config_h(self, filename):
        templ = RecursiveTemplate('configvariables.h', resource_filename(Requirement.parse("iotile-build"), "iotile/build/config/templates"))
        templ.add({'configvars': self.configs})
        out = templ.format_temp()

        shutil.move(out, filename)

    def generate_config_c(self, filename):
        templ = RecursiveTemplate('configvariables.c', resource_filename(Requirement.parse("iotile-build"), "iotile/build/config/templates"))
        templ.add({'configvars': self.configs})
        out = templ.format_temp()

        shutil.move(out, filename)

    def generate_config_defaults_as(self, filename):
        templ = RecursiveTemplate('config_defaults_asm.as', resource_filename(Requirement.parse("iotile-build"), "iotile/build/config/templates"))
        templ.add({'configvars': self.configs})
        out = templ.format_temp()

        shutil.move(out, filename)

    def _find_include_file(self, filename):
        for d in self.include_dirs:
            path = os.path.join(d, filename)
            if os.path.isfile(path):
                return path

        raise ArgumentError("Could not find included mib file", filename=filename, search_dirs=self.include_dirs)

    def _add_cmd(self, num, symbol, num_ints, has_buffer):
        handler = TBHandler.Create(symbol=symbol, ints=num_ints, has_buffer=has_buffer)
        
        if num in self.commands:
            raise DataError("Attempted to add the same command number twice", number=num, old_handler=self.commands[num], new_handler=handler)

        self.commands[num] = handler

    def _parse_cmd(self, match):
        symbol = match['symbol']

        num = self._parse_number(match['cmd_number'])
        if num < 0 or num >= 2**16:
            raise DataError("Invalid command identifier, must be a number between 0 and 2^16 - 1.", command_id=num)

        has_buffer = match['has_buffer']
        num_ints = match['num_ints']

        self._add_cmd(num, symbol, num_ints=num_ints, has_buffer=has_buffer)

    def _parse_include(self, match):
        filename = match['filename']

        path = self._find_include_file(filename)
        self._parse_file(path)

    def _parse_number(self, number):
        if isinstance(number, int):
            return number

        if number in self.variables:
            return self.variables[number]

        raise DataError("Reference to undefined variable %s" % number)

    def _parse_interface(self, match):
        interface = match['interface']
        if interface in self.interfaces:
            raise DataError("Attempted to add the same interface twice", interface=interface)

        self.interfaces.append(interface)

    def _parse_assignment(self, match):
        var = match['variable']
        val = match['value']
        if isinstance(val, basestring) and val[0] == '"':
            val = val[1:-1]
        else:
            val = self._parse_number(match['value'])

        self.variables[var] = val

    def _convert_value_to_bytes(self, value, type):
        """
        Given an integer, convert it to an array of bytes
        """

        if isinstance(value, int) or isinstance(value, long):
            fmt = '<%s' % (type_codes[type])
            output = struct.pack(fmt, value)
        elif isinstance(value, basestring):
            return bytearray(value)
        else:
            output_vals = []
            for x in value:
                out = self._convert_value_to_bytes(x, type)
                output_vals.append(out)

            output = [x for itembytes in output_vals for x in itembytes]

        return bytearray(output)

    def _parse_configvar(self, match):

        if 'length' in match:
            quantity = match['length']
            array = True
        else:
            quantity = 1
            array = False

        #FIXME: Properly handle all of the different cases here for arrays, strings and bare values
        if 'value' in match:
            default_bytevalue = self._convert_value_to_bytes(match['value'], match['type'])
            default_value = match['value']
            required = False
        else:
            default_value = None
            required = True

        varname = match['configvar']
        vartype = match['type']
        varnum = match['confignum']

        varsize = quantity*type_lengths[vartype]

        flags = len(self.configs)

        if flags >= 64:
            raise DataError("Too many configuration variables.  The maximum number of supported variables is 64")
        if required:
            flags |= (1 << 6)


        config = {'name': varname, 'flags': flags, 'type': vartype, 'array': array, 'total_size': varsize, 'count': quantity, 'required': required, 'default_value': default_value}

        if varnum in self.configs:
            raise DataError("Attempted to add the same config variable twice", variable_name=varname, id_number=varnum, defined_variables=self.configs.keys())
        
        self.configs[varnum] = config


    def _parse_line(self, line):
        matched = statement.parseString(line)

        if 'symbol' in matched:
            self._parse_cmd(matched)
        elif 'filename' in matched:
            self._parse_include(matched)
        elif 'variable' in matched:
            self._parse_assignment(matched)
        elif 'interface' in matched:
            self._parse_interface(matched)
        elif 'configvar' in matched:
            self._parse_configvar(matched)

    def _validate_information(self):
        """
        Validate that all information has been filled in
        """

        needed_variables = ["ModuleName", "ModuleVersion", "APIVersion"]

        for var in needed_variables:
            if var not in self.variables:
                raise DataError("Needed variable was not defined in mib file.", variable=var)

        #Make sure ModuleName is <= 6 characters
        if len(self.variables["ModuleName"]) > 6:
            raise DataError("ModuleName too long, must be 6 or fewer characters.", module_name=self.variables["ModuleName"])

        if not isinstance(self.variables["ModuleVersion"], basestring):
            raise ValueError("ModuleVersion ('%s') must be a string of the form X.Y.Z" % str(self.variables['ModuleVersion']))

        if not isinstance(self.variables["APIVersion"], basestring):
            raise ValueError("APIVersion ('%s') must be a string of the form X.Y" % str(self.variables['APIVersion']))


        self.variables['ModuleVersion'] = self._convert_module_version(self.variables["ModuleVersion"])
        self.variables['APIVersion'] = self._convert_api_version(self.variables["APIVersion"])
        self.variables["ModuleName"] = self.variables["ModuleName"].ljust(6)

        self.valid = True

    def _convert_version(self, version_string):
        vals = [int(x) for x in version_string.split(".")]

        invalid = [x for x in vals if x < 0 or x > 255]
        if len(invalid) > 0:
            raise DataError("Invalid version number larger than 1 byte", number=invalid[0], version_string=version_string)

        return vals

    def _convert_module_version(self, version):
        vals = self._convert_version(version)
        if len(vals) != 3:
            raise DataError("Invalid Module Version, should be X.Y.Z", version_string=version)

        return vals

    def _convert_api_version(self, version):
        vals = self._convert_version(version)
        if len(vals) != 2:
            raise DataError("Invalid API Version, should be X.Y", version_string=version)

        return vals     

    def get_block(self, config_only=False):
        """
        Create a TileBus Block based on the information in this descriptor
        """

        mib = block.TBBlock()

        for id, config in self.configs.iteritems():
            mib.add_config(id, config)

        if not config_only:
            for key, val in self.commands.iteritems():
                mib.add_command(key, val)

            for interface in self.interfaces:
                mib.add_interface(interface)

            if not self.valid:
                self._validate_information()
            
            mib.set_api_version(*self.variables["APIVersion"])
            mib.set_module_version(*self.variables["ModuleVersion"])
            mib.set_name(self.variables["ModuleName"])

        return mib
