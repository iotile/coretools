#exceptions.py

class TimeoutException:
	def __init__(self, where):
		self.message = "Timeout occured in %s" % where
		self.where = where

class RPCException:
	def __init__(self, type, data):
		self.type = type
		self.data = data