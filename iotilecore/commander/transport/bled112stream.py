# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from iotilecore.commander.transport.bled112dongle import BLED112Dongle
from iotilecore.commander.transport.cmdstream import CMDStream
from iotilecore.commander.commands import RPCCommand
from iotilecore.exceptions import *
from iotilecore.commander.exceptions import *
from iotilecore.utilities.packed import unpack
import atexit 
import uuid

class BLED112Stream (CMDStream):
	def __init__(self, port, mac=None):
		self.port = port
		self.mac = mac
		self.connected = False
		self.dongle = BLED112Dongle(self.port)
		self.boardopen = True
		
		if mac is not None:
			self.connect_mac(mac)

	def connect_mac(self, mac):
		if self.connected:
			raise HardwareError("Cannot connect to device when we are already connected")

		self.conn = self.dongle.connect(mac, timeout=6.0)			

		self.mac = mac
		self.connected = True

		self.services = self.dongle.probe_device(self.conn)

		#Check and see if we're using a new style btle protocol or the old mldp based one
		if self.dongle.TileBusService in self.services:
			self.protocol = "tilebus"
			self.dongle.set_notification(self.conn, self.services[self.dongle.TileBusService]['characteristics'][self.dongle.TileBusReceiveHeaderCharacteristic], True)
			self.dongle.set_notification(self.conn, self.services[self.dongle.TileBusService]['characteristics'][self.dongle.TileBusReceivePayloadCharacteristic], True)
		else:
			self.protocol = "mldp"
			self.dongle.start_mldp(self.conn, self.services, version="v1")
		
		atexit.register(self.close)

	def _send_rpc(self, address, feature, command, *args, **kwargs):
		if not self.connected:
			raise HardwareError("Cannot send an RPC until we are connected to a device")

		rpc = RPCCommand(address, feature, command, *args)

		payload = rpc._format_args()
		payload = payload[:rpc.spec]

		try:
			if self.protocol == "mldp":
				response = self.dongle.send_mib_packet(self.conn, self.services, address, feature, command, payload, **kwargs)
			else:
				response = self.dongle.send_tilebus_packet(self.conn, self.services, address, feature, command, payload, **kwargs)
			
			status = ord(response[0])

			#Only read the length of the packet if the has data bit is set
			#If no one responds, the length is 0 as well
			if status == 0xFF and ord(response[1]) == 0xFF:
				length = 0
			elif (status & 1 << 7):
				length = ord(response[3])
			else:
				length = 0
		
			mib_buffer = response[4:4+length]
			assert len(mib_buffer) == length

			return status, mib_buffer
		except TimeoutError:
			if address == 8:
				raise ModuleNotFoundError(address)
			else:
				raise HardwareError("Timeout waiting for a response from the remote BTLE module", address=address, feature=feature, command=command)

	def _enable_streaming(self):
		if not self.connected:
			raise HardwareError("Cannot enable streaming until we are connected to a device")

		if self.protocol == 'tilebus':
			self.dongle.set_notification(self.conn, self.services[self.dongle.TileBusService]['characteristics'][self.dongle.TileBusStreamingCharacteristic], True)
			self.dongle.stream_enabled = True

			return self.dongle._get_streaming_queue()
		else:
			raise HardwareError("Transport protocol does not support streaming")

	def close(self):
		if self.boardopen:
			self.dongle.disconnect(self.conn)
			self.dongle.io.close()
			self.boardopen = False

	def _scan(self):
		found_devs = self.dongle.scan()

		iotile_devs = {}

		#filter devices based on which ones have the iotile service characteristic
		for dev in found_devs:
			scan_data = dev['scan_data']

			if len(scan_data) < 29:
				continue

			#Make sure the scan data comes back with an incomplete UUID list
			if scan_data[0] != 17 or scan_data[1] != 6:
				continue

			uuid_buf = scan_data[2:18]
			assert(len(uuid_buf) == 16)
			service = uuid.UUID(bytes_le=str(uuid_buf))

			if service == self.dongle.TileBusService:
				#Now parse out the manufacturer specific data
				manu_data = scan_data[18:]
				assert (len(manu_data) == 11)

				length, datatype, manu_id, device_uuid, voltage, flags = unpack("<BBHLHB", manu_data)
				iotile_devs[device_uuid] = dev['address'] 

		return iotile_devs
