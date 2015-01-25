#list.py

class list(object):
	def __init__(self, valuetype, **kwargs):
		
		self.valuetype = valuetype
		self.type_system = kwargs['type_system']

	@staticmethod
	def Build(*types, **kwargs):
		if len(types) != 1:
			raise ValueError("list must be created with 1 argument, a value type")
		
		return list(types[0], **kwargs)

	def convert(self, value, **kwargs):
		converted = []
		for x in value:
			y = self.type_system.convert_to_type(x, self.valuetype, **kwargs)
			converted.append(y)

		return converted

	def default_formatter(self, value, **kwargs):
		lines = []
		for x in value:
			line = self.type_system.format_value(x, self.valuetype, **kwargs)
			lines.append(line)

		return "\n".join(lines)
