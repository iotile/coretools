#Transport layer for momo commander.  Should be able to send a stream of bytes
#and list whether any fsu devices are presently connected

from pymomo.commander.exceptions import *

class Transport:
	def read_until(self, chars):
		buffer = ""

		while True:
			c = self.read()
			if len(c) == 0:
				raise TimeoutException("Transport.read_until, looking for %s" % chars)
						
			for x in chars:
				if ord(c) == x:
					return (buffer, c)

			buffer += c