
class MoMoException(Exception):
	"""
	All MoMo API routines, upon encountering unrecoverable errors,
	will throw an exception that is a subclass of this exception.
	All other exceptions are caught and rethrown as an APIError
	for consistency.  Calling methods can assume that all annotated
	API functions will throw only MoMoException subclasses as defined
	below.
	"""
	pass

class ValidationError(MoMoException):
	"""
	API routines can impose validation criteria on their arguments in 
	addition to requiring simply a certain type of argument.  A clasic
	example is the "path" type which can have validators like "readable"
	or "exists".  When validation fails, this error is thrown.
	"""

	def __str__(self):
		return "Parameter '%s' with value '%s' failed validation: %s" % (self.args[0], str(self.args[1]), self.args[2])

class ConversionError(MoMoException):
	"""
	All API functions take typed parameters.  Each type defines conversion 
	operators for python types that are logically related to it.  When no
	valid conversion exists for the data type passed, this error is thrown.
	"""

	def __str__(self):
		return "Parameter '%s' with value '%s' could not be converted: %s" % (self.args[0], str(self.args[1]), self.args[2])

class NotFoundError(MoMoException):
	"""
	Thrown when an attempt to execute an API method is made and the API
	method does not exist.
	"""

	def __str__(self):
		args = self.args
		if len(self.args) == 1:
			args = self.args[0]

		return "Could not find callable '%s' in current context" % str(args)

class TimeoutError(MoMoException):
	"""
	The method timed out, usually indicating that a communication failure
	occurred, either with another process or with a hardware module.
	"""

	def __str__(self):
		args = self.args
		if len(self.args) == 1:
			args = self.args[0]

		return "A Timeout occurred, context is: %s" % str(args)

class ArgumentError(MoMoException):
	"""
	The method could not be called with the arguments passed.  This
	differs from InternalError in that when ArgumentError is returned,
	it is known that these arguments can never work for this function.

	An example would be passing three arguments to a function requiring
	4 arguments.
	"""

	def __str__(self):
		args = self.args
		if len(self.args) == 1:
			args = self.args[0]

		return "Invalid arguments: %s" % str(args)

class InternalError(MoMoException):
	"""
	The method could not be completed with the user input passed for 
	an unexpected reason.  This does not signify a bug in the API 
	method code.  More details should be passed in the arguments 
	"""

	def __str__(self):
		args = self.args
		if len(self.args) == 1:
			args = self.args[0]

		return "An internal error occurred: %s" % str(args)

class APIError(MoMoException):
	"""
	An internal API error occured during the execution of the method.
	This should only be returned if the error was unforeseen and not
	caused in any way by user input.  If the problem is that a user 
	input is invalid for the API call, ValidationError should be
	thrown instead.  

	All instances of APIError being thrown are bugs that should be
	reported and fixed. 
	"""

	def __str__(self):
		args = self.args
		if len(self.args) == 1:
			args = self.args[0]

		return "A bug occured in an API function: %s" % str(args)