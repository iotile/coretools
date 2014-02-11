#MIB Proxy Objects

def MIBProxyObject:
	def __init__(self, stream, address):
		self.stream = stream
		self.addr = address