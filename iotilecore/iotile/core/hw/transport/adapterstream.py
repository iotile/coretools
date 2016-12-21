"""An adapter class that takes a DeviceAdapter and produces a CMDStream compatible interface
"""
from copy import deepcopy
import Queue
from cmdstream import CMDStream
import datetime
from iotile.core.exceptions import HardwareError

class AdapterCMDStream(CMDStream):
    """An adapter class that takes a DeviceAdapter and produces a CMDStream compatible interface
    
    DeviceAdapters have a more generic interface that is not restricted to exclusive use in an online
    fashion by a single user at a time.  This class implements the CMDStream interface on top of a
    DeviceAdapter.
    
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
        self._reports = None

        self.adapter.add_callback('on_scan', self._on_scan)
        self.adapter.add_callback('on_report', self._on_report)

        super(AdapterCMDStream, self).__init__(port, connection_string, record)

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

    def _connect(self, uuid_value):
        if uuid_value not in self._scanned_devices:
            raise HardwareError("Could not find device to connect to by UUID", uuid=uuid_value)

        connstring = self._scanned_devices[uuid_value]['connection_string']
        self._connect_direct(connstring)

    def _connect_direct(self, connection_string):
        res = self.adapter.connect_sync(0, connection_string)
        if not res['success']:
            raise HardwareError("Could not connect to device", reason=res['failure_reason'], connection_string=connection_string)

        try:
            res = self.adapter.open_interface_sync(0, 'rpc')
        except Exception as exc:
            self.adapter.disconnect_sync(0)
            raise HardwareError("Could not open RPC interface on device due to an exception", exception=str(exc))

        if not res['success']:
            self.adapter.disconnect_sync(0)
            raise HardwareError("Could not open RPC interface on device", reason=res['failure_reason'], connection_string=connection_string)

    def _disconnect(self):
        self.adapter.disconnect_sync(0)
        self.adapter.periodic_callback()

    def _send_rpc(self, address, feature, cmd, payload, **kwargs):
        timeout = 3.0
        if 'timeout' in kwargs:
            timeout = float(kwargs['timeout'])

        result = self.adapter.send_rpc_sync(0, address, (feature << 8) | cmd, payload, timeout)
        success = result['success']
        status = result['status']
        payload = result['payload']

        if not success:
            raise HardwareError("Could not send RPC", reason=result['failure_reason'])

        return status, payload

    def _send_highspeed(self, data, progress_callback):
        self.adapter.send_script_sync(0, str(data), progress_callback)

    def _enable_streaming(self):
        self._reports = Queue.Queue()
        res = self.adapter.open_interface_sync(0, 'streaming')
        if not res['success']:
            raise HardwareError("Could not open streaming interface to device", reason=res['failure_reason'])

        return self._reports

    def _on_report(self, conn_id, report):
        if self._reports is None:
            return

        self._reports.put(report)

    def _close(self):
        self.adapter.stop_sync()
