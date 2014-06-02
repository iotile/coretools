class ValidationError(Exception):
	def __str__(self):
		return "Parameter '%s' with value '%s' failed validation: %s" % (self.args[0], str(self.args[1]), self.args[2])

class ConversionError(Exception):
	def __str__(self):
		return "Parameter '%s' with value '%s' could not be converted: " % (self.args[0], str(self.args[1]), self.args[2])

class NotFoundError(Exception):
	def __str__(self):
		return "Could not find callable '%s' in current context" % (self.args)

class TimeoutError(Exception):
	def __str__(self):
		return "A Timeout occurred, context is: %s" % (self.args)

class APIError(Exception):
	def __str__(self):
		return "An internal error occured in an API function: %s" % (self.args)