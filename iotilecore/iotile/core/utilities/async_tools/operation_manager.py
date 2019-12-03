"""Message driven asynchronous state machines.

This module allows you to define a complex operation that blocks at certain
points to wait for one or more messages to be received.  There can be
many operations running in parallel and multiple operations can be triggered
by the same message.  Messages are just dictionaries and the matching can
be according to any keys in the messages.

The OperationManager class is designed to provide a friendly API on which to
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
from iotile.core.exceptions import ArgumentError, InternalError
from . import event_loop


class MessageSpec:
    __slots__ = ['fields']

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
        self._should_pause = set()
        self._loop = loop
        self._logger = logging.getLogger(__name__)
        self._pause_count = 0
        self._messages = deque()
        self._dispatch_lock = loop.create_lock()
        self._process_pending = False

    def _add_waiter(self, spec, responder=None, pause=False):

        if responder is not None and pause is True:
            raise ArgumentError("You can only pause after waiting for future based waiters")

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

        if pause:
            self._should_pause.add(responder)

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

        if future in self._should_pause:
            self._should_pause.remove(future)

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

    def wait_for(self, timeout=None, pause=False, unpause=False, **kwargs):
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
            pause (bool): Pause the delivery of messages after receiving the message
                that this method is waiting for.
            unpause (bool): Unpause message delivery before waiting for messages.
            **kwargs: Keys to match in the message with their corresponding values.
                You must pass at least one keyword argument so there is something
                to look for.

        Returns:
            awaitable: The response
        """

        if len(kwargs) == 0:
            raise ArgumentError("You must specify at least one message field to wait on")

        spec = MessageSpec(**kwargs)
        future = self._add_waiter(spec, pause=pause)
        future.add_done_callback(lambda x: self._remove_waiter(spec, future))

        if unpause:
            self.unpause()

        return asyncio.wait_for(future, timeout=timeout)

    async def gather_until(self, gather_specs, until, timeout=None, *, pause=False, unpause=False):
        """Gather all matching messages until a message matching until is given or a timeout.

        This method allows you to accumulate messages matching the ``MessageSpec`` objects in
        ``gather_specs`` until a message matching the MessageSpec ``until`` is seen or a
        timeout occurs.

        Args:
            gather_specs (Iterable(MessageSpec)): The message specs that should be accumulated
            until (MessageSpec): The message spec that signals the end of gathering.  This will
                not be returend unless you also include the same message spec in ``gather_specs``.
            timeout (float): The maximum amount of time to wait for a message matching ``until``
                before giving up.  This is in seconds.
            pause (bool): Pause the delivery of messages after receiving the message
                that this method is waiting for.
            unpause (bool): Unpause message delivery before waiting for messages.

        Returns:
            list(object): A list of the gathered messages.

        Raises:
            asyncio.TimeoutError: The timeout expired before a message matching ``until`` was seen.
        """

        accum = []

        def _accum_message(message):
            accum.append(message)

        handles = []
        for spec in gather_specs:
            resp = self._add_waiter(spec, _accum_message)
            handles.append((spec, resp))

        future = self._add_waiter(until, pause=pause)
        future.add_done_callback(lambda x: self._remove_waiter(until, future))

        if unpause:
            self.unpause()

        try:
            await asyncio.wait_for(future, timeout=timeout)
        finally:
            for spec, resp in handles:
                self._remove_waiter(spec, resp)

        return accum

    async def gather_count(self, gather_specs, count, timeout=None, *, pause=False, unpause=False):
        """Gather all matching messages until a fixed number have been received.

        This method waits until an exact number of messages matching any of the specs in ``gather_specs``
        is received or a timeout occurs.

        Args:
            Args:
            gather_specs (Iterable(MessageSpec)): The message specs that should be accumulated
            count (int): The number of matching messages to wait for.
            timeout (float): The maximum amount of time to wait for a message matching ``until``
                before giving up.  This is in seconds.
            pause (bool): Pause the delivery of messages after receiving the message
                that this method is waiting for.
            unpause (bool): Unpause message delivery before waiting for messages.

        Returns:
            list(object): A list of the messages that were gathered.

            If this method returns normally the list will always have exactly ``count`` entries.

        Raises:
            asyncio.TimeoutError: The timeout expired before ``count`` matching messages were seen.
        """

        accum = []
        done = self._loop.create_event()

        def _accum_message(message):
            accum.append(message)

            if len(accum) == count:
                done.set()
                if pause:
                    self.pause()

        handles = []
        for spec in gather_specs:
            resp = self._add_waiter(spec, _accum_message)
            handles.append((spec, resp))

        if unpause:
            self.unpause()

        try:
            await asyncio.wait_for(done.wait(), timeout=timeout)
        except asyncio.TimeoutError as err:
            raise asyncio.TimeoutError("Timeout waiting for gathering fixed number of messages (%d of %d received)"
                                       " pause_count=%d"
                                       % (len(accum), count, self._pause_count)) from err
        finally:
            for spec, resp in handles:
                self._remove_waiter(spec, resp)

        return accum

    async def process_message(self, message, wait=True):
        """Process a message to see if it wakes any waiters.

        This will check waiters registered to see if they match the given
        message.  If so, they are awoken and passed the message.  All matching
        waiters will be woken.

        This method returns False if the message matched no waiters so it was
        ignored.

        All waiters for a given message are run in parallel with no guaranteed
        ordering.  However, it is guaranteed that all coroutines that were
        triggered by this message have run until completion by the time this
        method returns.

        If any waiters were configured to pause processing after they matched
        a message, this OperationManager will be paused when this method
        returns.

        Args:
            message (dict or object): The message that we should process
            wait (bool): Whether to wait for the message handlers to finish
                running. Defaults to True.

        Returns:
            bool: True if at least one waiter matched, otherwise False.
        """

        to_check = deque([self._waiters])
        ignored = True

        processors = list()

        while len(to_check) > 0:
            context = to_check.popleft()

            waiters = context.get(OperationManager._LEAF, [])
            for waiter in waiters:
                if isinstance(waiter, asyncio.Future):
                    if waiter in self._should_pause:
                        self.pause()

                    waiter.set_result(message)
                else:
                    proc = _launch(waiter, message, wait)
                    if proc is not None:
                        processors.append(proc)

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

        if len(processors) > 0 and wait:
            results = await asyncio.gather(*processors, return_exceptions=True)
            for proc, result in zip(processors, results):
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    self._logger.error("Error running processor %s: %s", proc, result)

        return not ignored

    async def process_all(self):
        """Process all messages that have been queued.

        You can queue messages using queue_message_threadsafe.  This method
        will drain the queue and process them all one at a time.  This method
        is automatically called as needed by queue_message_threadsafe and
        pause/unpause so it should not ever need to be called manually outside
        of testing scenarios.

        Only a single call to process all can be running at a time to ensure
        that messages are always dispatched in order without race conditions.
        """

        self._process_pending = False

        async with self._dispatch_lock:
            while len(self._messages) > 0:
                if self._pause_count > 0:
                    return

                current = self._messages.popleft()
                await self.process_message(current)

    def queue_message_threadsafe(self, message):
        """Queue a message for processing."""

        self._messages.append(message)
        if not self._process_pending:
            self._process_pending = True

            if self._pause_count == 0:
                self._loop.launch_coroutine(self.process_all)

    def pause(self):
        """Request to pause the dispatch of messages.

        This method increases an internal pause counter.  As long as the pause
        count is greater than 0, no messages will be dispatched through
        process_all().  This is used in combination with routines like gather_until()
        to make sure messages don't get processed in between when one operation finishes
        and you setup the next operation.
        """

        self._pause_count += 1

    def unpause(self):
        """Undo a previous call to pause().

        This method decreases the internal pause request counter.  When the counter
        reaches 0, message processing is allowed again.
        """

        if self._pause_count == 0:
            raise InternalError("Mismatched usage of pause/unpause, unpause called when not paused")

        self._pause_count -= 1
        if self._pause_count == 0 and len(self._messages) > 0:
            self._loop.launch_coroutine(self.process_all)


_MISSING = object()

def _get_key(obj, key, default=_MISSING):
    if isinstance(obj, dict):
        return obj.get(key, default)

    if hasattr(obj, key):
        return getattr(obj, key)

    return default


def _launch(coroutine_func, message, wait):
    result = coroutine_func(message)
    if inspect.isawaitable(result):
        if wait:
            return result

        asyncio.ensure_future(result)
        return None

    return None
