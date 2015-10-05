#descriptor.py
#A DSL for specifying log entries that can be used with the MoMo syslog module
#to log and debug system events in hardware.  Each log entry has a short message
#an optional description and an optional list of typed data items that follow it.

import pyparsing
from pyparsing import Word, Regex, nums, Literal, Optional, Group, QuotedString
from pymomo.exceptions import *
from pymomo.utilities.typedargs.annotate import context, param
from logdefinition import LogDefinition
from pymomo.utilities.template import RecursiveTemplate
import shutil
import os.path

symbol = Regex('[_a-zA-Z][_a-zA-Z0-9]*')

log_def = symbol("name")
log_text = QuotedString('"')
attribute_def = Literal('-').suppress() + QuotedString('"') + Literal('as').suppress() + Optional(Literal('list of')) + symbol('type') + Optional(Literal(',').suppress() + Literal("format").suppress() + symbol('format'))

statement = log_def | log_text | attribute_def

@context()
class LogDefinitionMap:
	"""
	A map defining known logging statement definitions.

	LogDefinitionMap contains a list of defined MoMo system_log logging statement types,
	including how to interpret the arguments that accompany the statement. This object
	is built by interpreting one or more Log Definition Files (.ldf).
	"""

	def __init__(self):
		self.entries = {}
		self.sources = []

	@param("file", "path", "readable", desc='Path of an ldf file to parse and add to this map')
	def add_ldf(self, file):
		"""
		Parse and add the specified LDF file.

		Adds the file to this LogDefinitionMap, throwing an exception if
		there is a collision with existing definitions.
		"""

		with open(file, "r") as f:
			lines = f.readlines()

		current_definition = None
		for line in lines:
			line = line.strip()
			if line == '':
				continue

			try:
				match = statement.parseString(line)

				#If we are starting a new statement and we have an existing one, try 
				#to add it to the map
				if 'name' in match:
					if current_definition is not None:
						self._add_definition(current_definition)

					current_definition = LogDefinition()
					current_definition.name = match['name']
				elif 'type' in match:
					offset = 0
					is_list = False
					if match[1] == 'list of':
						offset = 1
						is_list = True

					name = match[0]
					type = match[1+offset]
					format = None
					if "format" in match:
						format = match['format']

					if current_definition is None:
						raise InternalError("Invalid data definition outside of LogDefinition", line=line)

					if current_definition.contains_list():
						raise InternalError("You cannot specify a data definition after a list since lists have arbitrary length", line=line)
						
					current_definition.add_data(name, type, format, is_list=is_list)
				else:
					if current_definition is None:
						raise InternalError("Invalid log message outside of LogDefinition", line=line)

					current_definition.message = match[0]
			except pyparsing.ParseException as e:
				raise InternalError("Error parsing ldf file", file=file, line=e.lineno, column=e.col, reason=str(e))

		if current_definition is not None:
			self._add_definition(current_definition)

		self.sources.append(file)

	def _add_definition(self, statement):
		"""
		Verify the LogDefinition and add it to the map
		"""

		valid, reason = statement.validate()
		if not valid:
			raise InternalError("Invalid or incomplete LogDefinition", reason=reason, definition=statement)

		h = statement.hash()
		if h in self.entries:
			raise InternalError("Two log entry definitions hash to the same value, they must be distinct", 	first=self.entries[h].name, 
																											second=statement.name)
		self.entries[h] = statement

	@param("file", "path", "writeable", desc='output location for the header file')
	def generate_header(self, file):
		"""
		Generate a header file with these log statements
		"""

		name = os.path.basename(file)
		name = name.replace(' ', '_').replace('.', '_')

		vals = {"k"+v.name: "{0:#x}".format(h)+"UL"  for h,v in self.entries.iteritems()}

		templ = RecursiveTemplate('logdefinitions.h')
		templ.add({'messages': vals, 'sources': self.sources, 'name': name})
		out = templ.format_temp()

		shutil.move(out, file)

	@param("id", "integer", desc='the hashed message id to map')
	def map(self, id):
		"""
		Map a message id to its descriptive string and parameter list
		"""

		if id in self.entries:
			return self.entries[id]

		unknown = LogDefinition()
		unknown.name = "0x" + format(id, "08X")
		return unknown