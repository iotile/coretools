from collections import namedtuple
from pymomo.utilities import typedargs
import hashlib
from pymomo.exceptions import *

LogDataItem = namedtuple("LogDataItem", ['name', 'type', 'format', 'is_list'])

class LogDefinition:
	def __init__(self):
		self.name = None
		self.data = []
		self.message = None

	def validate(self):
		if not isinstance(self.name, basestring) or len(self.name) == 0:
			return False, "Invalid or missing name"

		if not isinstance(self.message, basestring) or len(self.message) == 0:
			return False, "Invalid or missing log message"

		return True, ""

	def contains_list(self):
		lists = filter(lambda x: x.is_list, self.data)
		return len(lists) > 0

	def assign_types(self, params):
		"""
		Assign types to the list of params if possible

		Given a list of parameters, attempt to match them with
		parameters based on the type information in this LogDefinition.
		If assignment is not possible, raise an InternalError
		"""

		if not self.is_valid_length(params):
			raise InternalError("The number of params does not correspond with the definition", params=params, definitions=self.data)

		if self.contains_list():
			fixed = zip(self.data[:-1], params[:len(self.data)-1])
			list_type = self.data[-1]
			list_params = params[len(fixed):]

			listed = zip([list_type]*len(list_params), list_params)
			return fixed + listed
		
		return zip(self.data, params)

	def is_valid_length(self, params):
		"""
		Check if the parameter list could correspond with this definition
		"""

		if not self.contains_list():
			if len(self.data) != len(params):
				return False

			return True

		#Even if the list is empty there need to be enough params to match
		#the fixed definitions 
		if len(params) < len(self.data) - 1:
			return False

		return True

	def add_data(self, name, type, format, is_list=False):
		if not typedargs.is_known_type(type):
			raise ArgumentError("Parameter has unknown type", param=name, type=type)

		if format is not None and not typedargs.is_known_format(type, format):
			raise ArgumentError("Parameter has unknown format", param=name, type=type, format=format)

		definition = LogDataItem(name, type, format, is_list)
		self.data.append(definition)

	def hash(self):
		m = hashlib.md5()
		m.update(self.name)

		h = m.digest()

		l0 = ord(h[-1])
		l1 = ord(h[-2])
		l2 = ord(h[-3])
		l3 = ord(h[-4])

		return (l3 << 24) | (l2 << 16) | (l1 << 8) | l0