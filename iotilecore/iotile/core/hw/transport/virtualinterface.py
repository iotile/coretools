"""Virtual interfaces are ways to connect to a virtual IOTile device like a real one

Virtual things are different from Mock things in that mock things are designed specifically
to facilitate unit testing and hence do not allow for the complete configurability of behavior.
Virtual things are designed to allow the same level of configurability and robustness as a real
thing. 
"""

class VirtualIOTileInterface(object):
	"""A virtual interface that presents an IOTile device to the world

	An example of a virtual interface is a bluetooth adapter configured with
	a GATT server that implements the TileBus over BLE protocol allowing any
	BLE client to connect to this virtual IOTile device as if it were a real
	one.

	Args:
		device (VirtualIOTileDevice): The actual device implementation that this
			virtual interface is providing access to.
	"""

	def __init__(self):
		self.device = None

	def start(self, device):
		"""Begin allowing connections to a virtual IOTile device
		
		Args:
			device (VirtualIOTileDevice): The python object that implements the IOTile
				device functionality that we wish to allow interaction with.
		"""

		raise NotImplementedError("VirtualIOTileInterface subclass did not override start")

	def stop(self):
		"""Stop allowing connections to this virtual IOTile device
		"""
		
		raise NotImplementedError("VirtualIOTileInterface subclass did not override start")
