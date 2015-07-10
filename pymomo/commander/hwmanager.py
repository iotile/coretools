from pymomo.utilities.typedargs import *

from pymomo.commander.transport import *
from pymomo.commander.exceptions import *
from pymomo.exceptions import *
from pymomo.utilities.typedargs.annotate import param, return_type
from pymomo.commander.proxy.proxy import MIBProxyObject
import serial
from serial.tools import list_ports
import re
import inspect
import os.path
import imp

@context("HardwareManager")
class HardwareManager:
	"""
	A module for managing and interacting with MoMo Hardware

	This context provides tools to configure, control, debug and program
	any MoMo module.  Specific functionality can be implemented in dynamically
	loaded proxy objects that should be distributed with each MoMo hardware module.

	To create a HardwareManager, you need to pass a port string that describes the 
	method to be used to connect to the MoMo hardware. The method should specify the 
	name of the connection method optionally followed by a colon and any extra information
	possibly needed to connect using that method.

	Currently supported methods are:
	- Field Service Unit: you should pass fsu:<path to serial port or COMX on Windows>.
	  if you don't pass a serial port path, pymomo will attempt to guess it for you, which
	  usually works.  This is the default connection method if nothing is specified

	- No Underlying Transport: you should pass null.  Any attempt to communicate with an
	  actual hardware device will fail.  This is primarily/only useful for unit testing.
	"""

	@param("port", "string", desc="connection string to use (for a serial port, the path to the port or COMX name")
	def __init__(self, port="fsu"):
		transport, delim, arg = port.partition(':')

		self.transport = transport
		self.port = None
		if arg != "":
			self.port = arg

		self.stream = self._create_stream()
		self.proxies = {}
		self.name_map = {}

	@param("address", "integer", "positive", desc="numerical address of module to get")
	@param("check", "bool", desc="make sure this module exists and is the right type")
	@param("type", "string", desc="module type")
	def get(self, address, type, check=True):
		"""
		Create a proxy object for a MoMo module directly by address. 

		This routine does not talk to a momo controller and so type must be specified explicitly
		since it currently cannot be inferred automatically by just communicating with the module
		itself.

		If check is True (the default), then messages will be sent to the module to make 
		sure that it exists and is working.
		"""

		proxy = self._create_proxy(type, address)

		if check:
			proxy.status()

		return proxy

	@annotated
	def controller(self):
		"""
		Find an attached MoMo controller board and attempt to connect to it.
		"""

		con = self._create_proxy('MIBController', 8) #Controllers always have address 8
		con.hwmanager = self
		return con

	@return_type("bool")
	def heartbeat(self):
		"""
		Check whether the underlying command stream is functional
		"""

		return self.stream.heartbeat()

	@annotated
	def reset(self):
		"""
		Attempt to reset the underlying stream back to a known state
		"""

		self.stream.reset()

	@param("asserted", "bool", desc="Whether alarm should be asserted or released")
	def set_alarm(self, asserted):
		"""
		Assert or release the alarm line
		"""

		self.stream.set_alarm(asserted)

	@return_type("bool")
	def check_alarm(self):
		"""
		Check whether the alarm line is asserted
		"""

		return self.stream.check_alarm()

	@param("path", "path", "readable", desc="path to module to load")
	@return_type("integer")
	def add_proxies(self, path):
		"""
		Add all proxy objects defined in the python module located at path.

		The module is loaded and all classes that inherit from MIBProxyObject
		are loaded and can be used to interact later with modules of that type.

		Returns the total number of proxies added.
		"""

		d,p = os.path.split(path)

		p,ext = os.path.splitext(p)
		if ext != '.py' and ext != '.pyc' and ext != "":
			raise ArgumentError("Passed proxy module is not a python package or module (.py or .pyc)", path=path)

		try:
			fileobj,pathname,description = imp.find_module(p, [d])
			mod = imp.load_module(p, fileobj, pathname, description)
		except ImportError as e:
			raise ArgumentError("could not import module in order to load external proxy modules", module_path=path, parent_directory=d, module_name=p, error=str(e))

		num_added = 0
		for obj in filter(lambda x: inspect.isclass(x) and issubclass(x, MIBProxyObject) and x != MIBProxyObject, mod.__dict__.itervalues()):
			if obj.__name__ in self.proxies:
				raise ArgumentError("already imported a proxy object with the same name", name=obj.__name__, imported_proxies=self.proxies.keys())
			
			self.proxies[obj.__name__] = obj

			#Check if this object matches a specific shortened name so that we can 
			#automatically match a hw module to a proxy without user intervention
			if hasattr(obj, 'ModuleName'):
				short_name = obj.ModuleName()
				if short_name in self.name_map:
					self.name_map[short_name].append(obj)
				else:
					self.name_map[short_name] = [obj]

			num_added += 1

		return num_added

	def _get_serial_ports(self):
		return list_ports.comports()

	def get_proxy(self, short_name):
		"""
		Find a proxy type given its short name.

		If no proxy type is found, return None.
		"""

		if short_name not in self.name_map:
			return None

		return self.name_map[short_name][0]

	def _find_momo_serial(self):
		"""
		Iterate over all connected COM devices and return the first
		one that matches FTDI's Vendor ID (403)
		"""

		for port, desc, hwid in self._get_serial_ports():
			if (re.match( r"USB VID:PID=0?403:6015", hwid) != None) or (re.match( r".*VID_0?403.PID_6015", hwid) != None):
				return port

	def _create_proxy(self, proxy, address):
		"""
		Create a python proxy object to talk to a MoMo module with the given type
		at the given address.
		"""

		if proxy not in self.proxies:
			raise UnknownModuleTypeError("unknown proxy module specified", module_type=proxy, known_types=self.proxies.keys())

		proxy_class = self.proxies[proxy]
		return proxy_class(self.stream, address)

	def _create_stream(self):
		stream = None

		if self.transport == 'fsu':
			serial_port = self.port
			if serial_port == None:
				serial_port = self._find_momo_serial()
			if serial_port == None:
				raise NoSerialConnectionException(available_ports=self._get_serial_ports())

			stream = SerialTransport(serial_port)
			return FSUStream(stream)
		elif self.transport == 'rn4020':
			port,mac = self.port.split(',')
			
			port = port.strip()
			mac = mac.strip()
			return RN4020DevStream(port, mac)
		elif self.transport == 'null':
			return FSUStream(None)
		else:
			raise ArgumentError("unknown connection method specified in HardwareManager", transport=self.transport)
