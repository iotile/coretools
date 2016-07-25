# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from iotilecore.commander.exceptions import *

class CMDStream:
	"""
	Any physical method that supports talking to an IOTile based device

	All interactions with the IOTile device will be via one of the primitive operations defined in this
	class. Specific implementations may transfer the data in their own way and add additional layers 
	as needed. Examples of CMDStream implementations are:
	- the Field Service Unit communicating over a USB <-> Serial bridge
	- Bluetooth LE (directly)
	- Bluetooth LE by way of the RN4020 module connected to a USB port of the com
	"""

	def scan(self):
		"""
		Scan for connected device and return a list of UUIDs for all of the
		devices that were found.
		"""

		if not hasattr(self, '_scan'):
			raise StreamOperationNotSupportedError(command="scan")

		return self._scan()

	def send_rpc(self, address, feature, command, *args, **kwargs):
		if not hasattr(self, '_send_rpc'):
			raise StreamOperationNotSupportedError(command="send_rpc")

		status, payload = self._send_rpc(address, feature, command, *args, **kwargs)

		if status == 0:
			raise ModuleBusyError(address)
		elif status == 0xFF:
			raise ModuleNotFoundError(address)

		return status, bytearray(payload)

	def enable_streaming(self):
		if not hasattr(self, '_enable_streaming'):
			raise StreamOperationNotSupportedError(command="enable_streaming")

		return self._enable_streaming()

	def heartbeat(self):
		if not hasattr(self, '_heartbeat'):
			raise StreamOperationNotSupportedError(command="heartbeat")

		return self._heartbeat()

	def reset(self):
		if not hasattr(self, '_reset'):
			raise StreamOperationNotSupportedError(command="reset")

		self._reset()

	def close(self):
		if not hasattr(self, '_close'):
			raise StreamOperationNotSupportedError(command="close")