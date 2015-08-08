from pymomo.commander.proxy import proxy12
from pymomo.commander.exceptions import *
from pymomo.commander.types import *
from pymomo.utilities.console import ProgressBar
import struct
from pymomo.utilities.intelhex import IntelHex
from pymomo.utilities.typedargs import param, annotated, context, return_type, iprint
from pymomo.exceptions import *
from time import sleep, time

@context("GSMModule")
class GSMModule (proxy12.MIB12ProxyObject):
	"""
	GSM Communication Module 

	This module implements cellular connectivity over either sms or 2G data based around
	the quadband SIM9000 module.  Basic testing functionality is exposed as well as a
	turnkey streaming API for transparently sending data over the cell network to a remote
	server (or cell number).
	"""

	def __init__(self, stream, addr):
		super(GSMModule, self).__init__(stream, addr)
		self.name = 'GSM Module'
		self.rx_buffer_loc = 0x21f4
		self.rx_buffer_length = 100

	@param("destination", "string", desc="URL or phone number to send messages to")
	def set_destination(self, destination):
		"""
		Set the current destination of streams opened on this module


		"""

		for i in xrange(0, len(destination), 18):
			buf = destination[i:i+18]
			iprint("Setting Destination (offset %d): %s" % ( i, buf ))
			self.rpc(11, 4, i, buf)

	@annotated
	@return_type("string")
	def read_rx_buffer(self):
		buff = ''
		for i in xrange(self.rx_buffer_loc, self.rx_buffer_loc + self.rx_buffer_length, 20):
			res = self.rpc(0,3, i, result_type=(0,True))
			buff += res['buffer']

		return buff

	@param("destination", "string", desc="Stream destination")
	@param("length", "integer", desc="Length of stream")
	def open_stream(self, destination, length):
		self.set_destination(destination)

		res = self.rpc(11, 0, length, result_type=(1, False), timeout=5*60.0)
		if res['ints'][0] != 0:
			raise HardwareError("Could not open GSM stream", result_code=res['ints'][0])

	@param("destination", "string", desc="phone number or url")
	@param("text", "string", desc="data to send")
	def send_message(self, destination, text):
		"""
		Send a message to the given destination 

		Destination must have one of the following two forms:
		1. '+NUMBER' with no dashes or spaces, for example: +16506695211 in order to
		send a text message

		2. 'URL' prefixed with http:// in order to send an http post request
		"""

		apn = "m2m.tele2.com"

		iprint("Sending message '%s' to %s" % ( text, destination ))
		iprint("Setting APN: %s" % apn)
		self.rpc(10, 9, apn)

		self.set_destination(destination)

		start_time = time()
		iprint("Opening stream with length %d" % len(text))
		res = self.rpc(11, 0, len(text), result_type=(1, False), timeout=5*60.0)
		if res['ints'][0] != 0:
			raise HardwareError("Could not open GSM stream", result_code=res['ints'][0])

		end_time = time()

		iprint("Opening stream took %.1f seconds" % ((end_time - start_time),))

		for i in xrange(0, len(text), 20):
			if (len(text) - i) >= 20:
				buf = text[i:i+20]
			else:
				buf = text[i:]

			iprint("> Streaming data: '%s'" % buf)
			res = self.rpc(11, 1, buf, timeout=10.0, result_type=(1, False))
			if res['ints'][0] != 0:
				raise HardwareError("Could not stream data to GSM module", result_code=res['ints'][0])
		
		iprint("Closing stream")

		start_time = time()
		res = self.rpc(11, 2, timeout=4*60.0, result_type=(1, False))
		end_time = time()
		iprint("Closing stream took %.1f seconds" % ((end_time - start_time),))

		if res['ints'][0] != 0:
			raise HardwareError("Could not close GSM stream", result_code=res['ints'][0])


	@annotated
	def module_on(self):
		"""
		Turn on the GSM Module

		This takes about 10 seconds since the SIM900 module needs specific wait times
		for it to go through initialization steps.  The module begins looking for 
		network coverage immediately but this call does not wait for network registration
		to succeed before returning.  To ensure that you are registered on a network,
		call the register function after calling this function.
		"""

		res = self.rpc(10, 0, result_type=(1, False), timeout=15.0)

		if res['ints'][0] != 0:
			raise HardwareError("Could not turn on GSM module", error_code=res['ints'][0])

	@annotated
	def register(self):
		"""
		Ensure that the GSM module is registered on a network

		This call can block for up to two minutes in the worst case since registration
		can be quite slow on remote networks.  You must turn the GSM module on before
		calling this function by using the module_on function first.
		"""

		try:
			res = self.rpc(10, 1, timeout=(2*60.0 + 2), result_type=(1, False))

			if res['ints'][0] != 0:
				raise TimeoutError("Could not register on the network", error_code=res['ints'][0])
		except RPCError as e:
			raise HardwareError("Could not register to network, likely because the gsm module was not on")


	@annotated
	def module_off(self):
		res = self.rpc(10,5, timeout=7.0)

	@param("cmd", "string", desc="AT command to send")
	@param("timeout", "float", "nonnegative", desc="maximum time to wait (in seconds)")
	@return_type("string")
	def at_command(self, cmd, timeout=10.0):
		"""
		Send an AT command to the GSM module and wait for its response

		The GSM module must be on for this command to work.  Use the module_on function 
		to turn the module on.  The AT command should be passed to this function as a string
		*without* a final termination character like carriage return or newline.  The appropriate
		line ending is appended automatically inside the module. 

		The response to the command is returned as a string without any parsing.  If the at command
		takes longer than 5 seconds to execute, this command will timeout.  
		"""

		for i in xrange(0, len(cmd), 20):
			if (len(cmd) - i) >= 20:
				buf = cmd[i:i+20]
			else:
				buf = cmd[i:]

			res = self.rpc(10, 2, buf)

		res = self.rpc(10, 2, result_type=(0, True), timeout=timeout)
		return res['buffer']

	def debug(self):
		res = self.rpc(10,7, result_type=(0, True))

		return res['buffer']

	def set_apn(self,apn):
		res = self.rpc(10, 9, apn)

	def test_gprs(self):
		apn = "wap.cingular"

		print "> apn %s" % apn
		self.rpc(10, 9, apn)
		print "> testgprs"
		res = self.rpc(10,8, result_type=(0, True))

		return res['buffer']
