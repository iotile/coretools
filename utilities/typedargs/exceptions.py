
class MoMoException(Exception):
	"""
	All MoMo API routines, upon encountering unrecoverable errors,
	will throw an exception that is a subclass of this exception.
	All other exceptions are caught and rethrown as an APIError
	for consistency.  Calling methods can assume that all annotated
	API functions will throw only MoMoException subclasses as defined
	below.
	"""

	def __init__(self, msg, **kwargs):
		self.params = kwargs
		self.msg = msg
	
	def format(self):
		msg = "%s: %s" % (self.__class__.__name__, self.msg)

		if len(self.params) != 0:
			paramstring = "\n".join([str(key) + ": " + str(val) for key,val in self.params.iteritems()])
			msg += "\nAdditional Information:\n" + paramstring
		
		return msg

class ValidationError(MoMoException):
	"""
	API routines can impose validation criteria on their arguments in 
	addition to requiring simply a certain type of argument.  A clasic
	example is the "path" type which can have validators like "readable"
	or "exists".  When validation fails, this error is thrown.
	"""

	pass

class ConversionError(MoMoException):
	"""
	All API functions take typed parameters.  Each type defines conversion 
	operators for python types that are logically related to it.  When no
	valid conversion exists for the data type passed, this error is thrown.
	"""

	pass

class NotFoundError(MoMoException):
	"""
	Thrown when an attempt to execute an API method is made and the API
	method does not exist.
	"""

	pass

class TimeoutError(MoMoException):
	"""
	The method timed out, usually indicating that a communication failure
	occurred, either with another process or with a hardware module.
	"""

	pass

class ArgumentError(MoMoException):
	"""
	The method could not be called with the arguments passed.  This
	differs from InternalError in that when ArgumentError is returned,
	it is known that these arguments can never work for this function.

	An example would be passing three arguments to a function requiring
	4 arguments.
	"""

	pass

class InternalError(MoMoException):
	"""
	The method could not be completed with the user input passed for 
	an unexpected reason.  This does not signify a bug in the API 
	method code.  More details should be passed in the arguments 
	"""

	pass

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

	pass

class BuildError(MoMoException):
	"""
	There is an error with some part of the build system.  This does not
	mean that there is a compilation error but rather that a required part
	of the build process did not complete successfully.  This exception means
	that something is misconfigured.
	"""

	pass