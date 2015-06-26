from pymomo.commander.exceptions import *

class CMDStream:
	"""
	Any physical method that supports talking to a MoMo unit

	All interactions with the MoMo unit will be via one of the primitive operations defined in this
	class. Specific implementations may transfer the data in their own way and add additional layers 
	as needed. Examples of CMDStream implementations are:
	- the Field Service Unit communicating over a USB <-> Serial bridge
	- Bluetooth LE (directly)
	- Bluetooth LE by way of the RN4020 module connected to a USB port of the com
	"""

	def check_alarm(self):
		"""
		Check whether the alarm line is asserted

		Returns true if is asserted and false if it idle.  Note that the alarm line is active-low
		so asserted means a low value on the alarm line.
		"""

		if not hasattr(self, '_check_alarm'):
			raise HardwareError("Command stream selected does not support checking alarm status")

	def set_alarm(self, status):
		"""
		Assert the alarm line is status is true, release it if status is false

		Since the alarm line is open-collector, releasing the line here may not cause it to go high
		if someone else if asserting the line low.
		"""

		if not hasattr(self, '_set_alarm'):
			raise HardwareError("Command stream selected does not support setting the alarm line")

	def send_rpc(self, address, feature, command, *args):
		if not hasattr(self, '_send_rpc'):
			raise HardwareError("Command stream selected does not support sending RPCs")

	def heartbeat(self):
		if not hasattr(self, '_heartbeat'):
			raise HardwareError("Command stream selected does not support heartbeats")

	def reset(self):
		if not hasattr(self, '_reset'):
			raise HardwareError("Command stream selected does not support resetting itself")