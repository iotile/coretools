# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

# IOTile Exceptions

class IOTileException(Exception):
	"""
	All MoMo API routines, upon encountering unrecoverable errors,
	will throw an exception that is a subclass of this exception.
	All other exceptions are caught and rethrown as an APIError
	for consistency.  Calling methods can assume that all annotated
	API functions will throw only IOTileException subclasses as defined
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

	def format_msg(self):
		msg = self.msg
		if len(self.params) != 0:
			paramstring = "\n".join([str(key) + ": " + str(val) for key,val in self.params.iteritems()])
			msg += "\nAdditional Information:\n" + paramstring
		
		return msg

	def __str__(self):
		msg = self.format()
		return msg

class ValidationError(IOTileException):
	"""
	API routines can impose validation criteria on` their arguments in 
	addition to requiring simply a certain type of argument.  A clasic
	example is the "path" type which can have validators like "readable"
	or "exists".  When validation fails, this error is thrown.
	"""

	pass

class ConversionError(IOTileException):
	"""
	All API functions take typed parameters.  Each type defines conversion 
	operators for python types that are logically related to it.  When no
	valid conversion exists for the data type passed, this error is thrown.
	"""

	pass

class NotFoundError(IOTileException):
	"""
	Thrown when an attempt to execute an API method is made and the API
	method does not exist.
	"""

	pass

class TimeoutError(IOTileException):
	"""
	The method timed out, usually indicating that a communication failure
	occurred, either with another process or with a hardware module.
	"""

	pass

class ArgumentError(IOTileException):
	"""
	The method could not be called with the arguments passed.  This
	differs from InternalError in that when ArgumentError is returned,
	it is known that these arguments can never work for this function.

	An example would be passing three arguments to a function requiring
	4 arguments.
	"""

	pass

class DataError(IOTileException):
	"""
	The method relied on data pass in by the user and the data was invalid.

	This could be because a file was the wrong type or because a data provider
	returned an unexpected result.  The parameters passed with this exception
	provide more detail on what occurred and where.
	"""

	pass

class InternalError(IOTileException):
	"""
	The method could not be completed with the user input passed for 
	an unexpected reason.  This does not signify a bug in the API 
	method code.  More details should be passed in the arguments.
	"""

	pass

class APIError(IOTileException):
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

class BuildError(IOTileException):
	"""
	There is an error with some part of the build system.  This does not
	mean that there is a compilation error but rather that a required part
	of the build process did not complete successfully.  This exception means
	that something is misconfigured.
	"""

	pass

class TypeSystemError(IOTileException):
	"""
	There was an error with the MoMo type system.  This can be due to improperly
	specifying an unknown type or because the required type was not properly loaded
	from an external module before a function that used that type was needed.
	"""

	pass

class EnvironmentError(IOTileException):
	"""
	The environment is not properly configured for the MoMo API command that was called.
	This can be because a required program was not installed or accessible or because
	a required environment variable was not defined.
	"""

	pass

class HardwareError(IOTileException):
	"""
	There was an issue communicating with or controlling a MoMo hardware module.  This
	exception anchors a range of exceptions that refer to specific kinds of hardware issues.

	By catching this exception, you will catch any sort of hardware failure.  If you are
	interested in specific kinds of hardware errors, you can look for or catch subclasses
	of this exception.
	"""

	pass
