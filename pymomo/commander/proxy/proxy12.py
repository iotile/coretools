#proxy12.py
#Proxy object for all modules that have a mib12 executive

import proxy
from pymomo.utilities.typedargs.annotate import returns, param, annotated
from collections import namedtuple
from pymomo.commander.exceptions import *

#Printer functions for displaying return values.
def print_status(status):
	"""
	Break out executive status bits and print them.
	"""

	print "Executive Status Register"
	print "Serial Number: %d" % status.serial
	print "HW Type: %d" % status.hwtype
	print "First Application Row: %d" % status.approw
	print "Runtime Status: 0x%X" % status.status

	if status.trapped:
		print "\n***Module has crashed and is waiting for debugging; trap bit is set.***\n"
	else:
		print "\nModule is running normally.\n"

class MIB12ProxyObject (proxy.MIBProxyObject):
	"""
	Proxy object for all 8-bit PIC modules that run the pic12_executive.
	Executive functionality is implemented here.
	"""

	@returns(desc='application firmware checksum', data=True)
	def checksum(self):
		"""
		Get the 8-bit application checksum.
		"""
		return self.rpc(0,2, result_type=(1,False))['ints'][0]

	@returns(desc='module status register', data=True, printer=print_status)
	def status(self):
		"""
		Get the module status register.

		Returns executive version, runtime parameters, hw type, executive size and whether the module has crashed.
		"""

		res = self.rpc(0,4, result_type=(2,False))
		status = namedtuple("ExecutiveStatus", ['serial', 'hwtype', 'approw', 'status', 'trapped'])

		status.serial = res['ints'][0] & 0xFF
		status.hwtype = res['ints'][0] >> 8
		status.approw = res['ints'][1] & 0xFF
		status.status = res['ints'][1] >> 8
		status.trapped = bool(status.status & 1<<7) 

		return status

	@param('location','integer','positive',desc='RAM address to read')
	@param('type', 'string', ('list', ['uint8']), desc='Type of variable to read (supports: uint8)')
	@returns(desc='variable contents', data=True)
	def readram(self, location, type='uint8'):
		res = self.rpc(0,3, location, result_type=(0,True))
		return ord(res['buffer'][0])

	@annotated
	def reset(self):
		"""
		Reset the application module.
		"""

		try:
			self.rpc(0, 1)
		except RPCException as e:
			if e.type != 63:
				raise e 