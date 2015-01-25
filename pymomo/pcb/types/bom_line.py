import collections
import string

def convert(arg, **kwargs):
	if arg is None:
		return None

	if isinstance(arg, BOMLine):
		return arg
	elif isinstance(arg, collections.Sequence) and not isinstance(arg, basestring):
		return BOMLine(arg)

	raise ValueError("Creating a BOMLine from any type other than a BOMLine object or list of parts is not supported")

def default_formatter(arg, **kwargs):
	return str(arg)

class BOMLine:
	digits = frozenset(string.digits)

	def __init__(self, parts):
		self.parts = parts

		self.count = len(parts)
		proto = parts[0]

		self.manu = proto.manu
		self.mpn = proto.mpn
		self.package = proto.package
		self.desc = proto.desc
		self.dist = proto.dist
		self.distpn = proto.distpn
		self.value = proto.value
		self.refs = sorted([x.name for x in parts], key=self._ref_number)
		self.type = self._extract_ref_type()

		if len(self.refs) > 0:
			self.lowest = self._ref_number(self.refs[0])
		else:
			self.lowest = 0

	def _ref_number(self, id):
		"""
		Extract the numeric part of a reference number
		"""

		return int(''.join([c for c in id if c in BOMLine.digits]))

	def _extract_ref_type(self):
		if len(self.refs) == 0:
			return None

		r = self.refs[0]

		for i in xrange(0, len(r)):
			if not r[i].isalpha():
				break

		return r[:i]

	def __str__(self):
		return "%d %s: %s" % (self.count, self.desc, self.refs)
