from pymomo.exceptions import *
import struct
import datetime

class MessageEntry:
	Streams = {
	1: "CRITICAL",
	2: "DEBUG",
	3: "REMOTE",
	4: "AUDIT",
	5: "PERFORMANCE"
	}

	def __init__(self, buf):
		if len(buf) != 15:
			raise ValidationError("Wrong length for new log entry (typecode 0), should be 15", length=len(buf))

		stream, timestamp, msg, remote_source, remote_seq, res1, res2 = struct.unpack('<BLLBBHH', buf)

		self.stream = stream
		self.timestamp = datetime.datetime.fromtimestamp(timestamp + 946684800)
		self.msg = msg
		self.remote_source = remote_source
		self.remote_seq = remote_seq

		if self.stream not in MessageEntry.Streams:
			raise ValidationError("Unknown stream number for this log entry", stream=self.stream)

	def stream_name(self):
		return MessageEntry.Streams[self.stream]

	def __str__(self):
		msg = format(self.msg, "08X")
		return "%s (%s) 0x%s" % (self.stream_name(), self.timestamp, msg)


class RawLogEntry:
	"""
	A generic entry in the MoMo syslog logging system
	that can be created from a buffer dumped via an RPC
	call to the momo controller hardware.
	"""

	NewLogEntryType = 0
	ContinuationType = 1
	BlobType = 2
	IntegerListType = 3
	StringType = 4
	RemoteLogEndType = 5

	Parsers = {
		NewLogEntryType: MessageEntry
	}

	def __init__(self, buffer):
		if len(buffer) != 16:
			raise ValidationError("Buffer must be of length sizeof(GenericLogEntry) = 16 bytes", buffer=buffer)

		header = ord(buffer[0])
		self.data = buffer[1:]

		self._parse_header(header)

	def _parse_header(self, header):
		typecode = header & 0xF
		length = (header >> 4) & 0xF

		if length > 15:
			raise ValidationError("Buffer length too long in GenericLogEntry", length=length, typecode=typecode)

		self.data = self.data[:length]
		self.length = length
		self.typecode = typecode

		if typecode < 0 or typecode > 5:
			raise ValidationError("Invalid typecode in GenericLogEntry", typecode=typecode)

	def merge(self, other):
		if other.typecode != RawLogEntry.ContinuationType:
			raise ValidationError("You can only combine log entries that are ContinuationType", typecode=other.typecode)

		if self.typecode == RawLogEntry.NewLogEntryType:
			raise ValidationError("You cannot combine a NewLogEntry with another type of log entry")

		self.data += other.data
		self.length += other.length

	def __str__(self):
		if self.typecode == RawLogEntry.NewLogEntryType:
			return str(MessageEntry(self.data))

		dat = " ".join([format(ord(x), "02X") for x in self.data])
		rep = "LogEntry type %d (%s)" % (self.typecode, dat)
		return rep
