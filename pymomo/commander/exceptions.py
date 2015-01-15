#exceptions.py

class TimeoutException:
	def __init__(self, where):
		self.message = "Timeout occured in %s" % where
		self.where = where

class RPCException:
	def __init__(self, type, data):
		self.type = type
		self.data = data

	def __str__(self):
		return "RPC failed, code %s : %s" % (self.type, self.data)

class NoSerialConnectionException:
	def __init__(self, ports ):
		self.message = "No port specified and no valid USB device detected."
		self.ports = ports

	def __str__(self):
		return self.message

	def available_ports(self):
		return self.ports