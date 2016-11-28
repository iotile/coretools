# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from iotile.core.utilities.typedargs import *

from iotile.core.hw.transport import *
from iotile.core.hw.exceptions import *
from iotile.core.exceptions import *
from iotile.core.utilities.typedargs.annotate import param, return_type, finalizer
from iotile.core.hw.proxy.proxy import MIBProxyObject
from iotile.core.dev.registry import ComponentRegistry
import re
import inspect
import os.path
import imp
import sys
from iotile.core.utilities.packed import unpack

#FIXME: Update the docstring for this class
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

	@param("port", "string", desc="transport method to use in the format transport[:port[,connection_string]]")
	@param("record", "path", desc="Optional file to record all RPC calls and responses made on this HardwareManager")
	def __init__(self, port="none", record=None):
		transport, delim, arg = port.partition(':')

		self.transport = transport
		self.port = None
		if arg != "":
			self.port = arg

		self.record = record
		
		self.stream = self._create_stream()
		self._stream_queue = None
		self.proxies = {'MIBProxyObject': MIBProxyObject}
		self.name_map = {}

		self._setup_proxies()

	def _setup_proxies(self):
		"""
		Load in proxy module objects for all of the registered components on this system
		"""

		# Find all of the registered IOTile components and see if we need to add any proxies for them
		reg = ComponentRegistry()
		modules = reg.list_components()

		proxies = reduce(lambda x,y: x+y, [reg.find_component(x).proxy_modules() for x in modules], [])
		for prox in proxies:
			self.add_proxies(prox)

	@param("address", "integer", "positive", desc="numerical address of module to get")
	def get(self, address):
		"""
		Create a proxy object for a tile by address. 

		The correct proxy object is determined by asking the tile for its status information
		and looking up the appropriate proxy in our list of installed proxy objects
		"""

		tile = self._create_proxy('MIBProxyObject', address)
		name = tile.tile_name()

		# Check for none
		# Now create the appropriate proxy object based on the name of the tile 
		tile_type = self.get_proxy(name)
		if tile_type is None:
			raise HardwareError("Could not find proxy object for tile", name=name)
		
		tile = tile_type(self.stream, address)		
		return tile

	@annotated
	def controller(self):
		"""
		Find an attached IOTile controller and attempt to connect to it.
		"""

		con = self.get(8)		
		con._hwmanager = self
		
		return con

	@param("device_uuid", "integer", desc="UUID of the device we would like to connect to")
	def connect(self, device_uuid):
		"""Attempt to connect to a device by its UUID
		"""

		self.stream.connect(device_uuid)

	@annotated
	def disconnect(self):
		"""Attempt to disconnect from a device 
		"""

		self.stream.disconnect()

	@return_type("bool")
	def heartbeat(self):
		"""
		Check whether the underlying command stream is functional
		"""

		return self.stream.heartbeat()

	@annotated
	def enable_streaming(self):
		"""
		Enable streaming of sensor graph data over this interface
		"""

		self._stream_queue = self.stream.enable_streaming()

	@return_type("integer")
	def count_readings(self):
		if self._stream_queue is None:
			return 0

		return self._stream_queue.qsize()

	@annotated
	def reset(self):
		"""
		Attempt to reset the underlying stream back to a known state
		"""

		self.stream.reset()

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		self.stream.close()
		return False

	@finalizer
	def close(self):
		self.stream.close()

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

			#Don't load modules twice
			if p in sys.modules:
				mod = sys.modules[p]
			else:
				mod = imp.load_module(p, fileobj, pathname, description)
		except ImportError as e:
			raise ArgumentError("could not import module in order to load external proxy modules", module_path=path, parent_directory=d, module_name=p, error=str(e))

		num_added = 0
		for obj in filter(lambda x: inspect.isclass(x) and issubclass(x, MIBProxyObject) and x != MIBProxyObject, mod.__dict__.itervalues()):
			if obj.__name__ in self.proxies:
				continue #Don't readd proxies that we already know about

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

	@annotated
	@return_type("list(basic_dict)")
	def scan(self):
		"""
		Scan for available devices and print a dictionary of information about them
		"""

		devices = self.stream.scan()

		#FIXME: Use dictionary format in bled112stream to document information returned about devices
		return devices

	def get_proxy(self, short_name):
		"""
		Find a proxy type given its short name.

		If no proxy type is found, return None.
		"""

		if short_name not in self.name_map:
			return None

		return self.name_map[short_name][0]

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

		conn_string = None
		port = self.port
		if port is not None and "," in port:
			port, conn_string = port.split(',')

		if port is not None:
			port = port.strip()
		if conn_string is not None:
			conn_string = conn_string.strip()

		if self.transport == 'bled112':
			return BLED112Stream(port, conn_string, record=self.record)
		elif self.transport == 'none':
			return CMDStream(None, None, record=self.record)
		elif self.transport == 'ws':
			return WebSocketStream(port, conn_string, record=self.record)
		elif self.transport == 'recorded':
			return RecordedStream(port, conn_string, record=self.record)
		else:
			raise ArgumentError("unknown connection method specified in HardwareManager", transport=self.transport)
