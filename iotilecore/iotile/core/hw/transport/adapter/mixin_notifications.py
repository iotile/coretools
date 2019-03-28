"""Mixin for adding basic event notifications to a DeviceAdapter."""

import inspect
import uuid
import itertools
from iotile.core.exceptions import ArgumentError


class BasicNotificationMixin:
    """A mixin that adds notification support to a DeviceAdapter.

    This mixin class implements the required abstract methods in
    :class:`AbstractDeviceAdapter` related to adding, adjusting and removing
    monitors as well as providing a private method: ``_notify_callback``
    that can trigger those monitors.

    Note that there are not locks inside any of the monitor registraton or
    adjustment procedures so they are only safe to call from within the
    BackgroundEventLoop that is calling the notifications.  This is to ensure
    that the registration/adjustment methods don't need to be coroutines but
    can guarantee to take effect before the next call to ``_notify_callback``.

    .. important::

        There are two requirements on a class that integrates this mixin.

        The class must have a _logger attribute pointing to a logging.Logger
        instance that will be used to log errors.

        It also requires that the class implement a _get_conn_id(conn_string)
        method that can turn a connection_string into a connection id or None
        if there is not an active connection to that device.

    Args:
        loop (BackgroundEventLoop): The loop we should use to perform
            notifications.
    """

    SUPPORTED_EVENTS = frozenset(['report', 'connection', 'trace', 'disconnection',
                                  'device_seen', 'broadcast'])
    SUPPORTED_ADJUSTMENTS = frozenset(['add', 'remove'])

    def __init__(self, loop):
        self._loop = loop
        self._monitors = {
        }
        self._callbacks = {}

        self._currently_notifying = False
        self._deferred_adjustments = []

    def register_monitor(self, devices, events, callback):
        """Register a callback when events happen.

        If this method is called, it is guaranteed to take effect before the
        next call to ``_notify_event`` after this method returns.  This method
        is safe to call from within a callback that is itself called by
        ``notify_event``.

        See :meth:`AbstractDeviceAdapter.register_monitor`.
        """

        # Ensure we don't exhaust any iterables
        events = list(events)
        devices = list(devices)

        for event in events:
            if event not in self.SUPPORTED_EVENTS:
                raise ArgumentError("Unknown event type {} specified".format(event), events=events)

        monitor_id = str(uuid.uuid4())

        action = (monitor_id, "add", devices, events)
        self._callbacks[monitor_id] = callback

        if self._currently_notifying:
            self._deferred_adjustments.append(action)
        else:
            self._adjust_monitor_internal(*action)

        return monitor_id

    def _adjust_monitor_internal(self, handle, action, devices, events):
        if action == 'add':
            callback = self._callbacks.get(handle)
            if callback is None:
                self._logger.warning("_adjust_monitor_internal called with an invalid handle, ignoring", handle)

            _add_monitor(self._monitors, handle, callback, devices, events)
        elif action == "remove":
            empty_devices = _remove_monitor(self._monitors, handle, devices, events)

            for device in empty_devices:
                del self._monitors[device]
        elif action == "delete":
            devices, events = _find_monitor(self._monitors, handle)
            self._adjust_monitor_internal(handle, "remove", devices, events)

            if handle in self._callbacks:
                del self._callbacks[handle]
        else:
            pass

    def iter_monitors(self):
        """Iterate over all defined (conn_string, event, monitor) tuples."""

        for conn_string, events in self._monitors.items():
            for event, handlers in events.items():
                for handler in handlers:
                    yield (conn_string, event, handler)

    def adjust_monitor(self, handle, action, devices, events):
        """Adjust a previously registered callback.

        See :meth:`AbstractDeviceAdapter.adjust_monitor`.
        """

        events = list(events)
        devices = list(devices)

        for event in events:
            if event not in self.SUPPORTED_EVENTS:
                raise ArgumentError("Unknown event type {} specified".format(event), events=events)

        if action not in self.SUPPORTED_ADJUSTMENTS:
            raise ArgumentError("Unknown adjustment {} specified".format(action))

        action = (handle, action, devices, events)
        if self._currently_notifying:
            self._deferred_adjustments.append(action)
        else:
            self._adjust_monitor_internal(*action)

    def remove_monitor(self, handle):
        """Remove a previously registered monitor.

        See :meth:`AbstractDeviceAdapter.adjust_monitor`.
        """

        action = (handle, "delete", None, None)
        if self._currently_notifying:
            self._deferred_adjustments.append(action)
        else:
            self._adjust_monitor_internal(*action)

    async def notify_event(self, conn_string, name, event):
        """Notify that an event has occured.

        This method will send a notification and ensure that all callbacks
        registered for it have completed by the time it returns.  In
        particular, if the callbacks are awaitable, this method will await
        them before returning.  The order in which the callbacks are called
        is undefined.

        Args:
            conn_string (str): The connection string for the device that the
                event is associated with.
            name (str): The name of the event. Must be in SUPPORTED_EVENTS.
            event (object): The event object.  The type of this object will
                depend on what is being notified.
        """

        try:
            self._currently_notifying = True
            conn_id = self._get_conn_id(conn_string)

            event_maps = self._monitors.get(conn_string, {})
            wildcard_maps = self._monitors.get(None, {})

            wildcard_handlers = wildcard_maps.get(name, {})
            event_handlers = event_maps.get(name, {})

            for handler, func in itertools.chain(event_handlers.items(), wildcard_handlers.items()):
                try:
                    result = func(conn_string, conn_id, name, event)
                    if inspect.isawaitable(result):
                        await result
                except:  #pylint:disable=bare-except;This is a background function and we are logging exceptions
                    self._logger.warning("Error calling notification callback id=%s, func=%s", handler, func, exc_info=True)
        finally:
            for action in self._deferred_adjustments:
                self._adjust_monitor_internal(*action)

            self._deferred_adjustments = []
            self._currently_notifying = False

    def fire_event(self, conn_string, name, event):
        """Fire an event without waiting.

        This will move the notification to the background event loop and
        return immediately.  It is useful for situations where you cannot
        await notify_event but keep in mind that it prevents back-pressure
        when you are notifying too fast so should be used sparingly.
        """

        self._loop.log_coroutine(self.notify_event(conn_string, name, event))


def _find_monitor(monitors, handle):
    """Find all devices and events with a given monitor installed."""

    found_devs = set()
    found_events = set()

    for conn_string, device in monitors.items():
        for event, handles in device.items():
            if handle in handles:
                found_events.add(event)
                found_devs.add(conn_string)

    return found_devs, found_events


def _add_monitor(monitors, handle, callback, devices, events):
    """Add the given monitor to the listed devices and events."""

    for conn_string in devices:
        data = monitors.get(conn_string)
        if data is None:
            data = dict()
            monitors[conn_string] = data

        for event in events:
            event_dict = data.get(event)
            if event_dict is None:
                event_dict = dict()
                data[event] = event_dict

            event_dict[handle] = callback


def _remove_monitor(monitors, handle, devices, events):
    """Remove the given monitor from the listed devices and events."""

    empty_devices = []

    for conn_string in devices:
        data = monitors.get(conn_string)
        if data is None:
            continue

        for event in events:
            event_dict = data.get(event)
            if event_dict is None:
                continue

            if handle in event_dict:
                del event_dict[handle]

            if len(event_dict) == 0:
                del data[event]

        if len(data) == 0:
            empty_devices.append(conn_string)

    return empty_devices
