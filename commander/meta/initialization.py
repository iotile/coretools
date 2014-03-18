from pymomo.commander import transport, cmdstream
from pymomo.commander.proxy import *
from pymomo.commander.exceptions import *

import serial
from serial.tools import list_ports
import re

def get_controller(serial_port=None):
	"""
	Given serial port descriptor, create all of the necessary
	object to get a controller proxy module 
	"""

	if serial_port == None:
		serial_port = _find_momo_serial()
		if serial_port == None:
			raise NoSerialConnectionException( _get_serial_ports() )

	s = transport.SerialTransport(serial_port)
	c = cmdstream.CMDStream(s)

	con = MIBController(c)
	return con

def _get_serial_ports():
	return list_ports.comports()

def _find_momo_serial():
	"""
	Iterate over all connected COM devices and return the first
	one that matches FTDI's Vendor ID (403)
	"""

	for port, desc, hwid in _get_serial_ports():
		if (re.match( r"USB VID:PID=0?403:6015", hwid) != None) or (re.match( r".*VID_0?403.PID_6015", hwid) != None):
			return port