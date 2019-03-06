
from iotile.core.utilities.schema_verify import DictionaryVerifier, OptionsVerifier, StringVerifier, IntVerifier
from iotile.core.hw import HardwareManager
from iotile.core.exceptions import HardwareError
from .shared_resource import SharedResource


RESOURCE_ARG_SCHEMA = DictionaryVerifier(desc="hardware_manager arguments")
RESOURCE_ARG_SCHEMA.add_optional("port", StringVerifier("the port string to use to connect to devices"))
RESOURCE_ARG_SCHEMA.add_optional("connect", OptionsVerifier(StringVerifier(), IntVerifier(), desc="the uuid of the device to connect to"))
RESOURCE_ARG_SCHEMA.add_optional("connect_direct", OptionsVerifier(StringVerifier(), desc="the connection string of the device to connect to"))


class HardwareManagerResource(SharedResource):
    """A shared HardwareManager instance.

    Arguments:
        port (str): Optional port argument that should
            be used to connect to a DeviceAdapter.  If not
            specified, the virtual environment default is used.
        connect: (str or int): The UUID of a device to connect to
            when this resource is created and disconnect from when
            it is destroyed.  This is an optional parameter.  If
            it is not specified the HardwareManager is not connected
            upon creation.
        connect_direct: (str or int): The connection string of a device to connect 
            directly to when this resource is created and disconnect from 
            when it is destroyed.  This is an optional parameter.  If
            it is not specified the HardwareManager is not connected
            upon creation.
    """

    ARG_SCHEMA = RESOURCE_ARG_SCHEMA

    def __init__(self, args):
        super(HardwareManagerResource, self).__init__()

        self._port = args.get('port')
        self._connect_id = args.get('connect')
        self._connection_string = args.get('connect_direct')
        self.hwman = None

        if self._connect_id is not None and not isinstance(self._connect_id, int):
            self._connect_id = int(self._connect_id, 0)

    def open(self):
        """Open and potentially connect to a device."""

        self.hwman = HardwareManager(port=self._port)
        self.opened = True

        if self._connection_string is not None:
            try:
                self.hwman.connect_direct(self._connection_string)
            except HardwareError:
                self.hwman.close()
                raise

        elif self._connect_id is not None:
            try:
                self.hwman.connect(self._connect_id)
            except HardwareError:
                self.hwman.close()
                raise


    def close(self):
        """Close and potentially disconnect from a device."""

        if self.hwman.stream.connected:
            self.hwman.disconnect()

        self.hwman.close()
        self.opened = False
