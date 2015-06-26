#exceptions.py

import pymomo.exceptions

class TimeoutException:
	def __init__(self, where):
		self.message = "Timeout occured in %s" % where
		self.where = where

class RPCError (pymomo.exceptions.HardwareError):
	pass

class ModuleBusyError(RPCError):
	def __init__(self, address, **kwargs):
		super(ModuleBusyError, self).__init__("Module responded that it was busy", address=address, **kwargs)

class UnsupportedCommandError(RPCError):
	def __init__(self, **kwargs):
		super(UnsupportedCommandError, self).__init__("Module did not support the specified command", **kwargs)

class ModuleNotFoundError(RPCError):
	def __init__(self, address, **kwargs):
		super(ModuleNotFoundError, self).__init__("Module was not found or did not respond", address=address, **kwargs)

class StreamNotConnectedError(RPCError):
	def __init__(self, **kwargs):
		super(StreamNotConnectedError, self).__init__("Stream was not connected to any MoMo devices", **kwargs)

class StreamOperationNotSupportedError(RPCError):
	def __init__(self, **kwargs):
		super(StreamOperationNotSupportedError, self).__init__("Underlying command stream does not support the required operation", **kwargs)

class NoSerialConnectionException (pymomo.exceptions.EnvironmentError):
	def __init__(self, ports):
		self.message = "No port specified and no valid USB device detected."
		self.ports = ports

	def __str__(self):
		return self.message

	def available_ports(self):
		return self.ports

class UnknownModuleTypeError (pymomo.exceptions.TypeSystemError):
	pass
