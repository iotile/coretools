from logentry import RawLogEntry, MessageEntry
from descriptor import LogDefinitionMap
from pymomo.utilities.typedargs.annotate import *
from pymomo.utilities import typedargs

class LogEntry:
	"""
	An object representing a complete log entry 
	"""

	def __init__(self, msg):
		self.params = []
		self.header = msg

@context()
class SystemLog:
	"""
	A list of log entries from the MoMo system log

	The MoMo controller keeps an ordered list of timestamped
	logged events, which can contain arbitrary parameters. 
	This class encapsulates one such list and allows you to
	access, filter and display the log entries.
	"""

	@annotated
	def __init__(self, raw_entries):
		"""
		Go through all of the entries and merge continuations
		"""
		self.entries = []

		entries = []
		self._mapper = LogDefinitionMap()

		for entry in raw_entries:
			if len(entries) != 0 and entry.typecode == RawLogEntry.ContinuationType:
				entries[-1].merge(entry)
			else:
				entries.append(entry)

		self._combine_entries(entries)

	def _combine_entries(self, entries):
		"""
		Combine entries into logical logging events including parameters
		"""
		current = None

		for entry in entries:
			if entry.typecode == RawLogEntry.NewLogEntryType:
				if current is not None:
					self.entries.append(current)

				current = LogEntry(MessageEntry(entry.data))
			elif current is not None:
				if entry.typecode == RawLogEntry.IntegerListType:
					ints = self._parse_ints(entry)
					current.params.extend(ints)
				elif entry.typecode == RawLogEntry.StringType:
					current.params.append(('array', entry.data[:-1])) #Chomp extra '\0' at the end of string entries
				else:
					current.params.append(('array', entry.data))

		if current is not None:
			self.entries.append(current)

	def _format_params(self, entry, ldf):
		"""
		Attempt to format the parameters in this log entry.
		"""
		fmtd = None

		if ldf.is_valid_length(entry.params):
			fmtd = []

			try:
				typed_params = ldf.assign_types(entry.params)

				for desc, data in typed_params:
					s = typedargs.type_system.format_value(data[1], desc.type, desc.format)
					fmt = "%s: %s" % (desc.name, s)
					fmtd.append(fmt)
			except MoMoException:
				fmtd = None

		#If we were not successful in formatting the parameters, just print them
		if fmtd is None:
			fmtd = [str(x[1]) for x in entry.params]

		return fmtd

	def _parse_ints(self, entry):
		if entry.length % 2 != 0:
			raise ValidationError("Integerlist whose length was not a multiple of two found", entry=entry, length=entry.length)

		ints = []

		for i in xrange(0, entry.length, 2):
			low = ord(entry.data[i])
			high = ord(entry.data[i+1])

			val = ((high & 0xFF) << 8) | low
			ints.append(('integer', val))

		return ints

	@param("file", "path", "readable", desc='Path of an ldf file to use to parse this system log')
	def add_ldf(self, file):
		"""
		Add an ldf file to help parse log entries
		"""

		self._mapper.add_ldf(file)

	def __str__(self):
		val = ""

		for entry in self.entries:
			ldf = self._mapper.map(entry.header.msg)
			if ldf.message is not None:
				desc = ldf.message
			else:
				desc = ldf.name

			line = "%s (%s) %s\n" % (entry.header.stream_name(), entry.header.timestamp, desc)
			val += line

			#Format and print the parameters
			params = self._format_params(entry, ldf)
			for param in params:
				ind = " - "
				ind += param + '\n'
				val += ind

		return val.rstrip()

	@annotated
	def display(self):
		val = str(self)
		if val != "":
			print str(self)