from logstatement import LogStatement

class LogCaller (LogStatement):
	def __init__(self, statement, log):
		if len(statement['data']) != 2:
			raise ValueError('Invalid hex logging statement, data length != 2 (len=%d)' % len(statement['data']))

		addr_low = statement['data'][0]['value']
		addr_high = statement['data'][1]['value']

		self.address = addr_high*256 + addr_low
		log.current_address = self.address-1 		#We log the return address, which is the next instruction to be executed

	def keep(self):
		return False

	def format(self):
		#This just mutates Log object state, it prints nothing
		return None