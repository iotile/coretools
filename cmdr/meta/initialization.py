from pymomo.cmdr import transport, cmdstream
from pymomo.cmdr.proxy import *
from pymomo.cmdr.exceptions import *

def get_controller(serial_port):
	"""
	Given serial port descriptor, create all of the necessary
	object to get a controller proxy module 
	"""

	s = transport.SerialTransport(serial_port)
	c = cmdstream.CMDStream(s)

	con = MIBController(c)
	return con
