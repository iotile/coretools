"""A generic Bluetooth based DeviceAdapter implementation.

This class is designed to be subclassed and serve as the foundation for
DeviceAdapters based on top of bluetooth host hardware.  It implements the
necessary device adapter functionality assuming a compliant AbstractBLECentral
implementation.
"""

import asyncio
from typing import Union
from time import monotonic
from iotile.core.hw.transport import StandardDeviceAdapter
from iotile.core.hw.exceptions import DeviceAdapterError
from iotile.core.utilities.async_tools import SharedLoop
from ..interface import AbstractBLECentral, errors, messages
from .constants import TileBusService

class GenericBLEDeviceAdapter(StandardDeviceAdapter):
    CONNECT_TIMEOUT = 4.0
    CONNECT_RETRIES = 4
    ACTIVE_SCAN = False

    def __init__(self, central: AbstractBLECentral, *, loop=SharedLoop):
        super(GenericBLEDeviceAdapter, self).__init__(__name__, loop=loop)

        self._central = central

        # Setup default configuration options
        self.set_config('connect_timeout', self.CONNECT_TIMEOUT)
        self.set_config('connect_retries', self.CONNECT_RETRIES)
        self.set_config('active_scan', self.ACTIVE_SCAN)

    async def start(self):
        """Start the device adapter.

        See :meth:`AbstractDeviceAdapter.start`.
        """

        await self._central.start()

        try:
            # Install all of our event listeners
            self._central.events.every_match(self.on_advertisement, event='advertisement')
            await self._central.request_scan('adapter', self.get_config('active_scan'))
        except:
            await self._central.stop()
            raise

        # Convenience to make sure any advertisements received have made it all the way through CoreTools
        # This helps testability because it removes a potential race condition when using an emulated
        # ble central that sends advertisements immediately on request_scan() being called so that you
        # can immediately connect and have it work without needing a delay.
        await self._central.events.wait_idle()

    async def stop(self):
        """Stop the device adapter.

        See :meth:`AbstractDeviceAdapter.stop`.
        """

        #TODO: Properly stop all connections here
        await self._central.stop()

    async def connect(self, conn_id, connection_string):
        """Connect to a device.

        See :meth:`AbstractDeviceAdapter.connect`.
        """

        self._ensure_connection(conn_id, False)
        self._setup_connection(conn_id, connection_string)

        timeout = self.get_config('connect_timeout')
        retries = self.get_config('connect_retries')

        self._logger.info("Starting connection to device %s [%d max retries, %.1fs timeout]",
                          connection_string, retries, timeout)
        start_time = monotonic()

        for retry in range(0, retries):
            try:
                peripheral = await _wait_for(self._central.connect(connection_string), timeout, self._logger)
                self._track_property(conn_id, 'peripheral', peripheral)

                self._logger.info("Successful connection to device %s after %.3f total seconds and %d retries",
                                  connection_string, monotonic() - start_time, retry)
                return
            except errors.EarlyDisconnectError:
                self._logger.debug("Early disconnect on connection attempt %d to %s", retry + 1, connection_string)
                continue
            except asyncio.TimeoutError as err:
                self._teardown_connection(conn_id, force=True)
                raise DeviceAdapterError(conn_id, 'connect', 'timeout attempting to connect') from err
            except Exception as err:
                self._teardown_connection(conn_id, force=True)
                raise DeviceAdapterError(conn_id, 'connect', 'unknown error during connect') from err

        self._logger.debug("Failed bluetooth connection because of too many early disconnects")
        raise DeviceAdapterError(conn_id, 'connect', 'giving up after too many early disconnect errors')

    async def disconnect(self, conn_id):
        """Disconnect from a connected device.

        See :meth:`AbstractDeviceAdapter.disconnect`.
        """

        self._ensure_connection(conn_id, True)
        conn_string = self._get_property(conn_id, 'connection_string')

        try:
            await self._central.disconnect(conn_string)
        finally:
            self._teardown_connection(conn_id, force=True)

    async def open_interface(self, conn_id, interface):
        """Open an interface on an IOTile device.

        See :meth:`AbstractDeviceAdapter.open_interface`.
        """

        self._ensure_connection(conn_id, True)
        conn_string = self._get_property(conn_id, 'connection_string')

        self._logger.debug("Opening interface %s on device %s", interface, conn_string)
        # These interfaces are no-ops over a ble protocol
        if interface in ('script', 'debug'):
            return


        try:
            if interface == 'rpc':
                await self._central.manage_subscription(conn_string, TileBusService.RECEIVE_HEADER, True)
                await self._central.manage_subscription(conn_string, TileBusService.RECEIVE_PAYLOAD, True)
            elif interface == 'streaming':
                await self._central.manage_subscription(conn_string, TileBusService.STREAMING, True)
            elif interface == 'tracing':
                await self._central.manage_subscription(conn_string, TileBusService.TRACING, True)
            else:
                raise DeviceAdapterError(conn_id, 'open_interface {}'.format(interface),
                                         'not supported')
        except errors.BluetoothError as err:
            self._logger.debug("Failed open_interface %s due to bluetooth error on device %s",
                               interface, conn_string, exc_info=True)
            raise DeviceAdapterError(conn_id, 'open_interface {}'.format(interface), 'bluetooth error') from err
        except Exception as err:
            self._logger.warning("Unknown exception during open_interface %s on device %s",
                                 interface, conn_string, exc_info=True)
            raise DeviceAdapterError(conn_id, 'open_interface {}'.format(interface), 'unknown exception') from err

    async def close_interface(self, conn_id, interface):
        """Close an interface on this IOTile device.

        See :meth:`AbstractDeviceAdapter.close_interface`.
        """

        self._ensure_connection(conn_id, True)

        # These interfaces are no-ops over a ble protocol
        if interface in ('script', 'debug'):
            return

        conn_string = self._get_property(conn_id, 'connection_string')

        try:
            if interface == 'rpc':
                await self._central.manage_subscription(conn_string, TileBusService.RECEIVE_HEADER, False)
                await self._central.manage_subscription(conn_string, TileBusService.RECEIVE_PAYLOAD, False)
            elif interface == 'streaming':
                await self._central.manage_subscription(conn_string, TileBusService.STREAMING, False)
            elif interface == 'tracing':
                await self._central.manage_subscription(conn_string, TileBusService.TRACING, False)
            else:
                raise DeviceAdapterError(conn_id, 'close_interface {}'.format(interface),
                                         'not supported')
        except errors.BluetoothError as err:
            self._logger.debug("Failed close_interface %s due to bluetooth error on device %s",
                               interface, conn_string, exc_info=True)
            raise DeviceAdapterError(conn_id, 'close_interface {}'.format(interface), 'bluetooth error') from err
        except Exception as err:
            self._logger.warning("Unknown exception during open_interface %s on device %s",
                                 interface, conn_string, exc_info=True)
            raise DeviceAdapterError(conn_id, 'close_interface {}'.format(interface), 'unknown exception') from err

    async def send_rpc(self, conn_id, address, rpc_id, payload, timeout):
        """Send an RPC to a device.

        See :meth:`AbstractDeviceAdapter.send_rpc`.
        """

        self._ensure_connection(conn_id, True)
        conn_string = self._get_property(conn_id, 'connection_string')

        if self._get_property(conn_id, 'rpc_result') is not None:
            raise DeviceAdapterError(conn_id, 'send_rpc', 'an rpc is already in-progress')

        result = asyncio.Future()
        self._track_property(conn_id, 'rpc_result', result)

        try:
            await _wait_for(result, timeout, self._logger)
        finally:
            if conn_id in self._connections:
                self._track_property(conn_id, 'rpc_result', None)

    async def on_advertisement(self, advert_event: messages.AdvertisementObserved):
        advert = advert_event.advertisement

        #FIXME: Actually parse the advertisements here and discard non-iotile advertisements
        await self.notify_event(advert.sender, 'device_seen', dict(uuid=0, connection_string=advert.sender))

    async def on_rpc_event(self, event: Union[messages.NotificationReceived, messages.PeripheralDisconnected]):
        """Callback triggered whenever an event relevant to rpc processing happens."""

        conn_id = self._get_conn_id(event.link)
        # If the message pertains to a device we're not connected to, ignore it
        if conn_id is None:
            return

        rpc_future = self._get_property(conn_id, 'rpc_result')
        if rpc_future is None:
            return

        if rpc_future.done():
            return

        if isinstance(event, messages.NotificationReceived):
            if event.characteristic.uuid == TileBusService.RECEIVE_HEADER:
                self._track_property(conn_id, 'last_rpc_result', event.value)

                if len(event.value) != 5:
                    rpc_future.set_result((event.value, b''))
                    return

                status = event.value[0]
                length = event.value[3]
                if length == 0:
                    rpc_future.set_result(event.value, b'')
            elif event.characteristic.uuid == TileBusService.RECEIVE_PAYLOAD:
                header = self._get_property(conn_id, 'last_rpc_result')
                rpc_future.set_result(header, event.value)
        else:
            rpc_future.set_result(bytes())



async def _wait_for(future, timeout, logger):
    """Cleanly wait for a future and make sure it's properly cancelled on a timeout."""

    task = asyncio.ensure_future(future)

    try:
        return await asyncio.wait_for(task, timeout=timeout)
    except asyncio.TimeoutError as err:
        try:
            # This is needed on python < 3.7 since it does not wait for the cancelled task to finish
            await task
        except asyncio.CancelledError:
            pass
        except:
            # Keep the original TimeoutError but log that we had trouble cancelling the operation
            logger.warning("Error cleanly cancelling task %s after timeout", task, exc_info=True)

        raise err
