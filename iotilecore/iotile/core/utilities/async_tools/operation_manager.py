"""Message driven asynchronous state machines.

This module allows you to define a complex operation that blocks at certain
points to wait for one or more messages to be received.  There can be
many operations running in parallel and multiple operations can be triggered
by the same message.  Messages are just dictionaries and the matching can
be according to any keys in the messages.

The Operationmanager class is designed to provide a friendly API on which to
build complex, asynchronous network or hardware operations.

The prototypical use case is dealing with messages received from bluetooth low
energy hardware. There is a single channel over which all messages are
received but they are logically multiplexed to multiple different parallel
connections.

In each of those connections you could have multiple parallel operations
happening (such as sending data to one characteristics while reading data from
another).  Each of those operations could be a multi-step non-atomic process
where the step transitions consist of waiting for the receipt of one or more
messages.

Implementing these operations usually involves complex callback or
multithreading based code.  OperationManager provides a tailored API for
allowing a coroutine to block until a specific message is received (or one of
several messages are received).

The goal is to allow the creation of simple coroutines that can safely share
access to to the underlying multiplexed channel and clearly specify what
messages they are waiting for to continue their operation.
"""

import asyncio
import inspect
import logging
from collections import deque
from iotile.core.exceptions import ArgumentError
from . import event_loop


class MessageSpec:
    def __init__(self, **kwargs):
        self.fields = kwargs


class OperationManager:
    """Manage complex operations blocking on specific network messages.

    This utility class is designed to provide a friendly API on which to build
    complex, asynchronous network or hardware operations.  The prototypical
    use case is dealing with messages received from bluetooth low energy
    hardware.

    You pass it messages using the process_message() API, where a message can
    either be an object with properties or a dictionary.  Each message is then
    compared to see if anyone is waiting for that message and if so, the
    waiter is unblocked or a callback is called.

    The goal is to be able to write coroutines that cleanly block until a
    specific message is received or timeout safely.

    You can block on a message by calling OperationManager.wait_for() with a
    specification of the message you are looking for.  If you just want a
    callback every time a certain kind of message is received, use
    OperationManager.every_match().

    Args:
        loop (BackgroundEventLoop): The background event loop we should
            use to perform all callbacks and blocking waits.  If not specified,
            the global, shared event loop is used.
    """

    _LEAF = object()

    def __init__(self, loop=event_loop.SharedLoop):
        if not isinstance(loop, event_loop.BackgroundEventLoop):
            raise ArgumentError("loop must be a BackgroundEventLoop, was {}".format(loop))

        self._waiters = {}
        self._loop = loop
        self._logger = logging.getLogger(__name__)

    def _add_waiter(self, spec, responder=None):
        loc = self._waiters
        for key, value in sorted(spec.fields.items()):
            if key not in loc:
                loc[key] = {}

            loc = loc[key]
            if value not in loc:
                loc[value] = {}

            loc = loc[value]

        if OperationManager._LEAF not in loc:
            loc[OperationManager._LEAF] = set()

        if responder is None:
            responder = self._loop.create_future()

        loc[OperationManager._LEAF].add(responder)
        return responder

    def _remove_waiter(self, spec, future):
        loc = self._waiters

        parents = []

        for key, value in sorted(spec.fields.items()):
            parents.append((loc, key))

            loc = loc.get(key)
            if loc is None:
                return

            parents.append((loc, value))

            loc = loc.get(value)
            if loc is None:
                return

        futures = loc.get(OperationManager._LEAF)
        if futures is None or future not in futures:
            return

        futures.remove(future)
        if len(futures) > 0:
            return

        del loc[OperationManager._LEAF]

        for parent, key in reversed(parents):
            if len(parent[key]) is not None:
                return

            del parent[key]

    def waiters(self, path=None):
        """Iterate over all waiters.

        This method will return the waiters in unspecified order
        including the future or callback object that will be invoked
        and a list containing the keys/value that are being matched.

        Yields:
            list, future or callable
        """

        context = self._waiters

        if path is None:
            path = []

        for key in path:
            context = context[key]

        if self._LEAF in context:
            for future in context[self._LEAF]:
                yield (path, future)

        for key in context:
            if key is self._LEAF:
                continue

            yield from self.waiters(path=path + [key])

    def every_match(self, callback, **kwargs):
        """Invoke callback every time a matching message is received.

        The callback will be invoked directly inside process_message so that
        you can guarantee that it has been called by the time process_message
        has returned.

        The callback can be removed by a call to remove_waiter(), passing the
        handle object returned by this call to identify it.

        Args:
            callback (callable): A callable function that will be called as
                callback(message) whenever a matching message is received.

        Returns:
            object: An opaque handle that can be passed to remove_waiter().

            This handle is the only way to remove this callback if you no
            longer want it to be called.
        """

        if len(kwargs) == 0:
            raise ArgumentError("You must specify at least one message field to wait on")

        spec = MessageSpec(**kwargs)
        responder = self._add_waiter(spec, callback)

        return (spec, responder)

    def _add_temporary_waiter(self, spec):
        future = self._add_waiter(spec)
        future.add_done_callback(lambda x: self._remove_waiter(spec, future))

        return future

    def remove_waiter(self, waiter_handle):
        """Remove a message callback.

        This call will remove a callback previously registered using
        every_match.

        Args:
            waiter_handle (object): The opaque handle returned by the
                previous call to every_match().
        """

        spec, waiter = waiter_handle
        self._remove_waiter(spec, waiter)

    def clear(self):
        """Clear all waiters.

        This method will remove any current scheduled waiter with an
        asyncio.CancelledError exception.
        """

        for _, waiter in self.waiters():
            if isinstance(waiter, asyncio.Future) and not waiter.done():
                waiter.set_exception(asyncio.CancelledError())

        self._waiters = {}

    def wait_for(self, timeout=None, **kwargs):
        """Wait for a specific matching message or timeout.

        You specify the message by passing name=value keyword arguments to
        this method.  The first message received after this function has been
        called that has all of the given keys with the given values will be
        returned when this function is awaited.

        If no matching message is received within the specified timeout (if
        given), then asyncio.TimeoutError will be raised.

        This function only matches a single message and removes itself once
        the message is seen or the timeout expires.

        Args:
            timeout (float): Optional timeout, defaults to None for no timeout.
            **kwargs: Keys to match in the message with their corresponding values.
                You must pass at least one keyword argument so there is something
                to look for.

        Returns:
            awaitable: The response
        """

        if len(kwargs) == 0:
            raise ArgumentError("You must specify at least one message field to wait on")

        spec = MessageSpec(**kwargs)
        future = self._add_waiter(spec)
        future.add_done_callback(lambda x: self._remove_waiter(spec, future))

        return asyncio.wait_for(future, timeout=timeout)

    async def process_message(self, message, wait=True):
        """Process a message to see if it wakes any waiters.

        This will check waiters registered to see if they match the given
        message.  If so, they are awoken and passed the message.  All matching
        waiters will be woken.

        This method returns False if the message matched no waiters so it was
        ignored.

        Normally you want to use wait=True (the default behavior) to guarantee
        that all callbacks have finished before this method returns.  However,
        sometimes that can cause a deadlock if those callbacks would
        themselves invoke behavior that requires whatever is waiting for this
        method to be alive.  In that case you can pass wait=False to ensure
        that the caller of this method does not block.

        Args:
            message (dict or object): The message that we should process
            wait (bool): Whether to block until all callbacks have finished
                or to return once the callbacks have been launched.

        Returns:
            bool: True if at least one waiter matched, otherwise False.
        """

        to_check = deque([self._waiters])
        ignored = True

        while len(to_check) > 0:
            context = to_check.popleft()

            waiters = context.get(OperationManager._LEAF, [])
            for waiter in waiters:
                if isinstance(waiter, asyncio.Future):
                    waiter.set_result(message)
                else:
                    try:
                        await _wait_or_launch(self._loop, waiter, message, wait)
                    except:  #pylint:disable=bare-except;We can't let a user callback break this routine
                        self._logger.warning("Error calling every_match callback, callback=%s, message=%s",
                                             waiter, message, exc_info=True)

                ignored = False

            for key in context:
                if key is OperationManager._LEAF:
                    continue

                message_val = _get_key(message, key)
                if message_val is _MISSING:
                    continue

                next_level = context[key]
                if message_val in next_level:
                    to_check.append(next_level[message_val])

        return not ignored


_MISSING = object()

def _get_key(obj, key, default=_MISSING):
    if isinstance(obj, dict):
        return obj.get(key, default)

    if hasattr(obj, key):
        return getattr(obj, key)

    return default


async def _wait_or_launch(loop, coroutine_func, message, wait):
    result = coroutine_func(message)
    if inspect.isawaitable(result):
        if wait:
            await result
        else:
            loop.launch_coroutine(result)
