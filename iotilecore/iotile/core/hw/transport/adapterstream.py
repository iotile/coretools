"""An adapter class that takes a DeviceAdapter and produces a CMDStream compatible interface
"""
from copy import deepcopy
from adapter import DeviceAdapter
from cmdstream import CMDStream
import datetime

class AdapterCMDStream(CMDStream):
    """An adapter class that takes a DeviceAdapter and produces a CMDStream compatible interface
    
    DeviceAdapters have a more generic interface that is not restricted to exclusive use in an online
    fashion by a single user at a time.  This class implements the CMDStream interface.
    
    Args:
        adapter (DeviceAdapter): the DeviceAdatper that we should use to create this CMDStream
        port (string): the name of the port that we should connect through
        connection_string (string): A DeviceAdapter specific string specifying a device that we
            should immediately connect to
        record (string): The path to a file that we should use to record everything sent down
            this CMDStream
    """

    def __init__(self, adapter, port, connection_string, record=None):
        self.adapter = adapter
        self._scanned_devices = {}

        self.adapter.add_callback('on_scan', self._on_scan)

        super(AdapterCMDStream, self).__init__(adapter, port, connection_string, record)

    def _on_scan(self, adapter_id, info, expiration_time):
        """Callback called when a new device is discovered on this CMDStream

        Args:
            adapter_id (int): An ID for the adapter that scanned the device
            info (dict): Information about the scanned device
            expiration_time (float): How long this device should stay around
        """

        device_id = info['uuid']
        infocopy = deepcopy(info)

        infocopy['expiration_time'] = datetime.datetime.now() + datetime.timedelta(seconds=expiration_time)
        self._scanned_devices[device_id] = infocopy

    def _scan(self):
        to_remove = set()

        now = datetime.datetime.now()

        for name, value in self._scanned_devices.iteritems():
            if value['expiration_time'] < now:
                to_remove.add(name)

        for name in to_remove:
            del self._scanned_devices[name]

        return self._scanned_devices.values()
