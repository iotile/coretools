"""Mixin for adding basic event notifications to a DeviceAdapter."""

import inspect
import uuid
import itertools
from iotile.core.exceptions import ArgumentError


class BasicNotificationMixin:
    """A mixin that adds notification support to a DeviceAdapter.

    This mixin class implements the required abstract methods in
    :class:`AbstractDeviceAdapter` related to adding, adjusting and removing
        monitors as well as providing a method :meth:`notify_event` that can
        trigger those monitors.  For situations where you can't await a
        coroutine, there is also a wrapper :meth:`fire_event` that defers the
        notification to a later time inside the BackgroundEventLoop.

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

        If you also include the standard :class:`PerConnectionDataMixin` mixin
        in your adatper then your adapter will have a compliant implementation
        of ``_get_conn_id()`` and nothing else is needed.

    Args:
        loop (BackgroundEventLoop): The loop we should use to perform
            notifications.
    """

    SUPPORTED_EVENTS = frozenset(['report', 'connection', 'trace', 'disconnection',
                                  'device_seen', 'broadcast', 'progress'])
    SUPPORTED_ADJUSTMENTS = frozenset(['add', 'remove'])
    PROGRESS_OPERATIONS = frozenset(['debug', 'script'])

    def __init__(self, loop):
        self._loop = loop
        self._monitors = {}
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

    async def _notify_event_internal(self, conn_string, name, event):
        """Notify that an event has occured.

        This method will send a notification and ensure that all callbacks
        registered for it have completed by the time it returns.  In
        particular, if the callbacks are awaitable, this method will await
        them before returning.  The order in which the callbacks are called
        is undefined.

        This is a low level method that is not intended to be called directly.
        You should use the high level public notify_* methods for each of the
        types of events to ensure consistency in how the event objects are
        created.

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

    def notify_event(self, conn_string, name, event):
        """Notify an event.

        This method will launch a coroutine that runs all callbacks (and
        awaits all coroutines) attached to the given event that was just
        raised.  Internally it uses
        :meth:`BackgroundEventLoop.launch_coroutine` which retains an
        awaitable object when called from within an event loop and a
        concurrent Future object when called outside of the event loop.

        Calling this method from outside of the BackgroundEventLoop is
        considered experimental and not stable behavior that can be depended
        on.

        Args:
            conn_string (str): The connection string for the device that the
                event is associated with.
            name (str): The name of the event. Must be in SUPPORTED_EVENTS.
            event (object): The event object.  The type of this object will
                depend on what is being notified.

        Returns:
            awaitable: An awaitable object that can be used to wait for all callbacks.
        """

        return self._loop.launch_coroutine(self._notify_event_internal, conn_string, name, event)

    def notify_event_nowait(self, conn_string, name, event):
        """Notify an event.

        This will move the notification to the background event loop and
        return immediately.  It is useful for situations where you cannot
        await notify_event but keep in mind that it prevents back-pressure
        when you are notifying too fast so should be used sparingly.

        Note that calling this method will push the notification to a
        background task so it can be difficult to reason about when it will
        precisely occur.  For that reason, :meth:`notify_event` should be
        preferred when possible since that method guarantees that all
        callbacks will be called synchronously before it finishes.

        Args:
            conn_string (str): The connection string for the device that the
                event is associated with.
            name (str): The name of the event. Must be in SUPPORTED_EVENTS.
            event (object): The event object.  The type of this object will
                depend on what is being notified.
        """

        if self._loop.stopping:
            self._logger.debug("Ignoring notification %s from %s because loop is shutting down", name, conn_string)
            return

        self._loop.log_coroutine(self._notify_event_internal, conn_string, name, event)

    #pylint:disable=too-many-arguments;The final wait argument has a sane default
    def notify_progress(self, conn_string, operation, finished, total, wait=True):
        """Send a progress event.

        Progress events can be sent for ``debug`` and ``script`` operations and
        notify the caller about the progress of these potentially long-running
        operations.  They have two integer properties that specify what fraction
        of the operation has been completed.

        Args:
            conn_string (str): The device that is sending the event.
            operations (str): The operation that is in progress: debug or script
            finished (int): The number of "steps" that have finished.
            total (int): The total number of steps to perform.
            wait (bool): Whether to return an awaitable that we can use to
                block until the notification has made it to all callbacks.

        Returns:
            awaitable or None: An awaitable if wait=True.

            If wait is False, the notification is run in the background with
            no way to check its progress and None is returned.
        """

        if operation not in self.PROGRESS_OPERATIONS:
            raise ArgumentError("Invalid operation for progress event: {}".format(operation))

        event = dict(operation=operation, finished=finished, total=total)

        if wait:
            return self.notify_event(conn_string, 'progress', event)

        self.notify_event_nowait(conn_string, 'progress', event)
        return None


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
