from pymomo.commander import transport, cmdstream
from pymomo.commander.proxy import *
from pymomo.commander.exceptions import *

def get_controller(serial_port):
	"""
	Given serial port descriptor, create all of the necessary
	object to get a controller proxy module 
	"""

	s = transport.SerialTransport(serial_port)
	c = cmdstream.CMDStream(s)

	con = MIBController(c)
	return con
