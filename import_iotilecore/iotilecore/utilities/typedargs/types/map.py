# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#map.py
#a complex type wrapping a python dictionary

class map(object):
	def __init__(self, keytype, valuetype, **kwargs):
		
		self.keytype = keytype
		self.valuetype = valuetype
		self.type_system = kwargs['type_system']

	@staticmethod
	def Build(*types, **kwargs):
		if len(types) != 2:
			raise ValueError("map must be created with 2 arguments, a keytype and a valuetype")
		
		return map(types[0], types[1], **kwargs)

	def convert(self, value, **kwargs):
		if isinstance(value, dict):
			return value

		raise ValueError("Converting to map from string not yet supported")

	def default_formatter(self, value, **kwargs):
		forms = []
		for key,val in value.iteritems():
			keyform = self.type_system.format_value(key, self.keytype)
			valform = self.type_system.format_value(val, self.valuetype)
			forms.append("%s: %s" % (keyform, valform))

		return "\n".join(forms)