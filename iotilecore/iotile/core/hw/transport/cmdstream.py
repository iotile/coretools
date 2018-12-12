# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

import atexit
import binascii
from io import open
from datetime import datetime
from monotonic import monotonic
from iotile.core.hw.exceptions import StreamOperationNotSupportedError, ModuleBusyError, ModuleNotFoundError
from iotile.core.exceptions import HardwareError

class _RecordedRPC(object):
    """Internal helper class for saving recorded RPCs to csv files."""

    def __init__(self, connection, start, runtime, address, rpc_id, call, response=None, status=None, error=None):

        if isinstance(connection, bytes):
            connection = connection.decode('utf-8')

        self.connection = connection
        self.start = start
        self.runtime = runtime
        self.address = address
        self.rpc_id = rpc_id
        self.call = binascii.hexlify(call).decode('utf-8')

        self.response = u""
        if response is not None:
            self.response = binascii.hexlify(response).decode('utf-8')

        if status is None:
            status = -1

        self.status = status

        if error is None:
            error = u""

        self.error = error

    def serialize(self):
        """Convert this recorded RPC into a string."""

        return u"{},{: <26},{:2d},{:#06x},{:#04x},{:5.0f},{: <40},{: <40},{}".format(self.connection, self.start.isoformat(), self.address, self.rpc_id,
                                                                                     self.status, self.runtime * 1000, self.call, self.response, self.error)


open_streams = set()


def do_final_close():
    """
    Make sure that all streams are properly closed at shutdown
    """

    #Make a copy since stream.close will remove the stream from the master set
    streams = open_streams.copy()
    for stream in streams:
        stream.close()


atexit.register(do_final_close)


class CMDStream(object):
    """
    Any physical method that supports talking to an IOTile based device

    All interactions with the IOTile device will be via one of the primitive operations defined in this
    class. Specific implementations may transfer the data in their own way and add additional layers
    as needed. Examples of CMDStream implementations are:
    - the Field Service Unit communicating over a USB <-> Serial bridge
    - Bluetooth LE (directly)
    - Bluetooth LE by way of the RN4020 module connected to a USB port of the com
    """

    def __init__(self, port, connection_string, record=None):
        self.connection_string = connection_string
        self.connected = False
        self.port = port
        self.record = record
        self.opened = True

        open_streams.add(self)

        if self.record is not None:
            self._recording = []

        if self.connection_string != None:
            try:
                self.connect_direct(self.connection_string)
            except:
                self.close()
                raise

    def scan(self, wait=None):
        """Scan for available IOTile devices.

        Scan for connected device and return a map of UUIDs and connection strings for
        all of the devices that were found.

        Args:
            wait (float): Optional amount of time to force the device adapter to wait before
                returning.
        """

        if not hasattr(self, '_scan'):
            raise StreamOperationNotSupportedError(command="scan")

        return sorted(self._scan(wait=wait), key=lambda x: x['uuid'])

    def connect_direct(self, connection_string):
        """Directly connect to a device using its stream specific connection string
        """

        if self.connected:
            raise HardwareError("Cannot connect when we are already connected")

        if not hasattr(self, '_connect_direct'):
            raise StreamOperationNotSupportedError(command="connect_direct")

        self._connect_direct(connection_string)
        self.connected = True
        self.connection_string = connection_string

    def connect(self, uuid_value, wait=None):
        """Connect to a specific device by its uuid

        Attempt to connect to a device that we have previously scanned using its UUID.
        If wait is not None, then it is used in the same was a scan(wait) to override
        default wait times with an explicit value.

        Args:
            wait (float): Optional amount of time to force the device adapter to wait before
                atttempting to connect.
        """

        if self.connected:
            raise HardwareError("Cannot connect when we are already connected")

        if not hasattr(self, '_connect'):
            raise StreamOperationNotSupportedError(command="connect")

        connection_string = self._connect(uuid_value, wait=wait)

        self.connected = True
        self.connection_string = connection_string

    def disconnect(self):
        """Disconnect from the device that we are currently connected to
        """
        if not self.connected:
            raise HardwareError("Cannot disconnect when we are not connected")

        if not hasattr(self, '_disconnect'):
            raise StreamOperationNotSupportedError(command="disconnect")

        self._disconnect()
        self.connected = False

    def send_rpc(self, address, rpc_id, call_payload, **kwargs):
        if not self.connected:
            raise HardwareError("Cannot send an RPC if we are not in a connected state")

        if not hasattr(self, '_send_rpc'):
            raise StreamOperationNotSupportedError(command="send_rpc")

        if self.record is not None:
            start_time = monotonic()
            start_stamp = datetime.utcnow()

        try:
            status = -1
            payload = b''

            status, payload = self._send_rpc(address, rpc_id, call_payload, **kwargs)
        finally:
            #If we are recording this, save off the call and response
            if self.record is not None:
                end_time = monotonic()
                duration = end_time - start_time

                recording = _RecordedRPC(self.connection_string, start_stamp, duration, address, rpc_id,
                                         call_payload, payload, status)

                self._recording.append(recording)

        if status == 0:
            raise ModuleBusyError(address)
        elif status == 0xFF:
            raise ModuleNotFoundError(address)

        return status, bytearray(payload)


    def enable_streaming(self):
        if not self.connected:
            raise HardwareError("Cannot enable streaming if we are not in a connected state")

        if not hasattr(self, '_enable_streaming'):
            raise StreamOperationNotSupportedError(command="enable_streaming")

        return self._enable_streaming()

    def enable_broadcasting(self):
        """Prepare to receive broadcast reports and not discard them."""

        if not hasattr(self, '_enable_broadcasting'):
            raise StreamOperationNotSupportedError(command="enable_broadcasting")

        return self._enable_broadcasting()

    def enable_tracing(self):
        if not self.connected:
            raise HardwareError("Cannot enable tracing if we are not in a connected state")

        if not hasattr(self, '_enable_tracing'):
            raise StreamOperationNotSupportedError(command="enable_tracing")

        return self._enable_tracing()

    def enable_debug(self, connection_string=None):
        if not hasattr(self, '_enable_debug'):
            raise StreamOperationNotSupportedError(command="enable_debug")

        return self._enable_debug(connection_string)

    def debug_command(self, cmd_name, args=None, progress_callback=None):
        return self._debug_command(cmd_name, args, progress_callback)

    def send_highspeed(self, data, progress_callback=None):
        if not self.connected:
            raise HardwareError("Cannot send highspeed data if we are not in a connected state")

        if not hasattr(self, '_send_highspeed'):
            raise StreamOperationNotSupportedError(command="send_highspeed")

        return self._send_highspeed(data, progress_callback)

    def heartbeat(self):
        if not hasattr(self, '_heartbeat'):
            raise StreamOperationNotSupportedError(command="heartbeat")

        return self._heartbeat()

    def reset(self):
        if not hasattr(self, '_reset'):
            raise StreamOperationNotSupportedError(command="reset")

        self._reset()

    def close(self):
        if not self.opened:
            print("close called twice on the same stream")
            return

        # Do not raise an error if no internal _close routine is found, that
        # just means that no stream specific close operations are required
        try:
            if hasattr(self, '_close'):
                self._close()
        finally:
            #Make sure that no matter what happens we save this recording out
            self._save_recording()
            self.opened = False
            open_streams.remove(self)

    def _save_recording(self):
        if not self.record:
            return

        with open(self.record, "w", encoding="utf-8") as outfile:
            outfile.write(u"# IOTile RPC Recording\n")
            outfile.write(u"# Format: 1.0\n\n")
            outfile.write(u"Connection,Timestamp [utc isoformat],Address,RPC ID,Duration [ms],Status,Call,Response,Error\n")

            for recording in self._recording:
                outfile.write(recording.serialize())
                outfile.write(u'\n')

        self.record = False
