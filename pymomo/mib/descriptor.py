#descriptor.py
#Define a Domain Specific Language for specifying MIB endpoints

from pyparsing import Word, Regex, nums, Literal, Optional, Group
from handler import MIBHandler
import sys
import os.path
from pymomo.utilities.paths import MomoPaths
import block

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
strval = Regex('"[_a-zA-Z0-9]+"')
number = (Word(nums).setParseAction(lambda s,l,t: [int(t[0])])) | symbol
ints = number('num_ints') + Optional(Literal('ints') | Literal('int'))
has_buffer = (Literal('yes') | Literal('no')).setParseAction(lambda s,l,t: [t[0] == 'yes'])
comma = Literal(',').suppress()
left = Literal('(').suppress()
right = Literal(')').suppress()
colon = Literal(':').suppress()
comment = Literal('#')

assignment_def = symbol("variable") + "=" + (number('value') | strval('value')) + ';'
cmd_def = number("cmd_number") + colon + symbol("symbol") + left + ints + comma + has_buffer('has_buffer') + right + ";"
feat_def = Literal("feature") + number("feature_number")
include = Literal("#include") + left + filename("filename") + right

statement = include | cmd_def | feat_def | comment | assignment_def

class MIBDescriptor:
	"""
	Class that parses a .mib file which contains a DSL specifying the valid MIB endpoints
	in a MIB12 module and can output an asm file containing the proper MIB command map
	for that architecture.
	"""
	def __init__(self, filename):
		self.curr_feature = -1
		self.features = {}
		self.variables = {}

		self._parse_file(filename)

		for feature in self.features.keys():
			self._validate_feature(feature)
			self.features[feature] = [self.features[feature][i] for i in sorted(self.features[feature].keys())]

		self._validate_information()
	def _parse_file(self, filename):
		with open(filename, "r") as f:
			for l in f:
				line = l.lstrip().rstrip()

				if line == "":
					continue

				self._parse_line(line)

	def _add_feature(self, feature_var):
		feature = self._parse_number(feature_var)

		self.features[feature] = {}
		self.curr_feature = feature

	def _add_cmd(self, num, symbol, num_ints, has_buffer):
		handler = MIBHandler.Create(symbol=symbol, ints=num_ints, has_buffer=has_buffer)
		
		self.features[self.curr_feature][num] = handler

	def _parse_cmd(self, match):
		symbol = match['symbol']

		if self.curr_feature < 0:
			raise ValueError("MIB Command specified without first declaring a feature.")

		num = self._parse_number(match['cmd_number'])

		has_buffer = match['has_buffer']
		num_ints = match['num_ints']

		self._add_cmd(num, symbol, num_ints=num_ints, has_buffer=has_buffer)

	def _parse_include(self, match):
		filename = match['filename']

		folder = MomoPaths().config

		path = os.path.join(folder, filename)
		self._parse_file(path)

	def _parse_number(self, number):
		if isinstance(number, int):
			return number

		if number in self.variables:
			return self.variables[number]

		raise ValueError("Reference to undefined variable %s" % number)

	def _parse_assignment(self, match):
		var = match['variable']
		val = match['value']
		if isinstance(val, basestring) and val[0] == '"':
			val = val[1:-1]
		else:
			val = self._parse_number(match['value'])

		self.variables[var] = val

	def _parse_line(self, line):
		matched = statement.parseString(line)

		if 'feature_number' in matched:
			self._add_feature(matched['feature_number'])
		elif 'symbol' in matched:
			self._parse_cmd(matched)
		elif 'filename' in matched:
			self._parse_include(matched)
		elif 'variable' in matched:
			self._parse_assignment(matched)

	def _validate_feature(self, feature):
		curr_index = 0

		for i in sorted(self.features[feature]):
			if i != curr_index:
				raise ValueError("Feature %d has nonsequential command.  Must start at 0 and have no gaps. Command was %d, expected %d." % (feature, i, curr_index))

			curr_index += 1

	def _validate_information(self):
		"""
		Validate that all information has been filled in
		"""

		needed_variables = ["ModuleName", "ModuleFlags", "ModuleType"]

		for var in needed_variables:
			if var not in self.variables:
				raise ValueError("Needed variable %s was not defined in mib file." % var)

		#Make sure ModuleName is <= 7 characters
		if len(self.variables["ModuleName"]) > 7:
			raise ValueError("ModuleName ('%s') too long, must be less than 8 characters." % self.variables["ModuleName"])

		if not isinstance(self.variables["ModuleType"], int):
			raise ValueError("ModuleType ('%s') must be an integer." % str(self.variables['ModuleType']))

		if not isinstance(self.variables["ModuleFlags"], int):
			raise ValueError("ModuleFlags ('%s') must be an integer." % str(self.variables['ModuleFlags']))

		self.variables["ModuleName"] = self.variables["ModuleName"].ljust(7)

	def get_block(self):
		"""
		Create a MIB Block based on the information in this descriptor
		"""

		mib = block.MIBBlock()

		for feat, cmds in self.features.iteritems():
			for i,cmd in enumerate(cmds):
				mib.add_command(feat, i, cmd)

		mib.set_variables(	name=self.variables["ModuleName"], flags=self.variables["ModuleFlags"],
							type=self.variables["ModuleType"])

		return mib