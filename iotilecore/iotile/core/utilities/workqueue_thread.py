"""A thread that hands workqueue items to a user function."""

import threading
import logging
import sys
from collections import namedtuple
from queue import Queue
from future.utils import raise_
from iotile.core.exceptions import TimeoutExpiredError

STOP_WORKER_ITEM = object()
MarkLocationItem = namedtuple('MarkLocationItem', ['callback'])
WorkItem = namedtuple("WorkItem", ['arg', 'callback'])
WaitIdleItem = namedtuple("WaitIdleItem", ['callback'])


class WorkQueueThread(threading.Thread):
    """A worker thread that handles queued work.

    This class takes a single callable as a parameter in __init__
    and starts a background thread with a shared queue.  Whenever
    an item is put in the shared queue, the callable is called with
    that work item.

    The return value of that callable is passed back to the caller
    or given via a callback function.

    The key methods of this class are:

    - dispatch(item, callback=None): Synchronously dispatches a work item to
      the queue and waits for the result.  If callback is not None, this
      function will return immediately and the result will be passed to the
      callback when it is ready.
    - stop(): Synchronously stop the background thread.  This will wait for
      all currently queued work items to finish and then cleanly shut down the
      background thread.
    - flush(): Wait until the work queue is momentarily empty().  This method
      is useful for ensuring that all work items received up until this method
      was called have been processed.

    Args:
        handler (callable): The handler function that will be pasesd all of the
            work items queued in dispatch() and should return a result that will
            be the return value of dispatch().  If this function throws an exception,
            it will be rethrown from dispatch.
    """

    def __init__(self, handler):
        super(WorkQueueThread, self).__init__()
        self.daemon = True

        self._routine = handler
        self._work_queue = Queue()
        self._logger = logging.getLogger(__name__)

    def dispatch(self, value, callback=None):
        """Dispatch an item to the workqueue and optionally wait.

        This is the only way to add work to the background work queue. Unless
        you also pass a callback object, this method will synchronously wait
        for the work to finish and return the result. If the work raises an
        exception, the exception will be reraised in this method.

        If you pass an optional callback(exc_info, return_value), this method
        will not block and instead your callback will be called when the work
        finishes.  If an exception was raised during processing, exc_info will
        be set with the contents of sys.exc_info().  Otherwise, exc_info will
        be None and whatever the work_queue handler returned will be passed as
        the return_value parameter to the supplied callback.

        Args:
            value (object): Arbitrary object that will be passed to the work
                queue handler.

            callback (callable): Optional callback to receive the result of
                the work queue when it finishes.  If not passed, this method
                will be synchronous and return the result from the dispatch()
                method itself

        Returns:
            object: The result of the work_queue handler function or None.

            If callback is not None, then this method will return immediately
            with a None return value.  Otherwise it will block until the work
            item is finished (including any work items ahead in the queue) and
            return whatever the work item handler returned.
        """

        done = None

        if callback is None:
            done = threading.Event()
            shared_data = [None, None]

            def _callback(exc_info, return_value):
                shared_data[0] = exc_info
                shared_data[1] = return_value

                done.set()

            callback = _callback

        workitem = WorkItem(value, callback)
        self._work_queue.put(workitem)
        if done is None:
            return None

        done.wait()
        exc_info, return_value = shared_data
        if exc_info is not None:
            raise_(*exc_info)  #pylint:disable=not-an-iterable;We know it is iterable when done is not None

        return return_value

    def flush(self):
        """Synchronously wait until this work item is processed.

        This has the effect of waiting until all work items queued before this
        method has been called have finished.
        """

        done = threading.Event()

        def _callback():
            done.set()

        self.defer(_callback)
        done.wait()

    def defer(self, callback):
        """Schedule a callback once all current items in the queue are finished.

        This function can schedule work synchronous with the work queue without
        passing through the work queue handler.

        This method returns immediately.

        Args:
            callback (callable): A callable with no arguments that will be
                called once all current items in the workqueue have been
                executed.
        """

        self._work_queue.put(MarkLocationItem(callback))

    def defer_until_idle(self, callback):
        """Wait until the work queue is (temporarily) empty.

        This is different from flush() because processing a work queue entry
        may add additional work queue entries.  This method lets you wait
        until there are no more entries in the work queue.

        Depending on how work is being added to the work queue, this may be
        a very interesting condtion.

        This method will return immeidately and schedule callback to be called
        as soon as the work queue becomes empty.  You can queue as many
        callbacks as you like via multiple calls to defer_until_idle. These
        will be executed in the same order together the first time that the
        queue becomes momentarily idle.

        Note that the concept of an "empty" workqueue is a very unstable
        concept in general.  Unless you as the caller know that no one else
        except you and possibly the work-queue items themselves can add a task
        to the work queue, then there is no guarantee that this callback will
        ever fire since it could be that someone else is adding work queue
        items just as fast as they are being completed.

        This is a specialty method that is useful in a few defined
        circumstances.

        Args:
            callback (callable): A callable with no arguments that will be
                called once the queue is temporarily empty.
        """

        self._work_queue.put(WaitIdleItem(callback))

    def wait_until_idle(self):
        """Block the calling thread until the work queue is (temporarily) empty.

        See the detailed discussion under defer_until_idle() for restrictions
        and expected use cases for this method.

        This routine will block the calling thread.
        """

        done = threading.Event()

        def _callback():
            done.set()

        self.defer_until_idle(_callback)
        done.wait()

    def run(self):
        """The target routine called to start thread activity."""

        idle_watchers = []

        while True:
            try:
                if self._work_queue.empty() and len(idle_watchers) > 0:
                    for watcher in idle_watchers:
                        try:
                            watcher()
                        except: #pylint:disable=bare-except;We can't let one idle watcher failure impact any other watcher
                            self._logger.exception("Error inside queue idle watcher")

                    idle_watchers = []

                item = self._work_queue.get()

                # Handle special actions that are not RPCs
                if item is STOP_WORKER_ITEM:
                    return
                elif isinstance(item, MarkLocationItem):
                    item.callback()
                    continue
                elif isinstance(item, WaitIdleItem):
                    idle_watchers.append(item.callback)
                    continue
                elif not isinstance(item, WorkItem):
                    self._logger.error("Invalid item passed to WorkQueueThread: %s, ignoring", item)
                    continue

                try:
                    exc_info = None
                    retval = None

                    retval = self._routine(item.arg)
                except:  #pylint:disable=bare-except;We need to capture the exception and feed it back to the caller
                    exc_info = sys.exc_info()

                if item.callback is not None:
                    item.callback(exc_info, retval)
            except:  #pylint:disable=bare-except;We cannot let this background thread die until we are told to stop()
                self._logger.exception("Error inside background workqueue thread")

    def stop(self, timeout=None, force=False):
        """Stop the worker thread and synchronously wait for it to finish.

        Args:
            timeout (float): The maximum time to wait for the thread to stop
                before raising a TimeoutExpiredError.  If force is True, TimeoutExpiredError
                is not raised and the thread is just marked as a daemon thread
                so that it does not block cleanly exiting the process.
            force (bool): If true and the thread does not exit in timeout seconds
                no error is raised since the thread is marked as daemon and will
                be killed when the process exits.
        """

        self.signal_stop()
        self.wait_stopped(timeout, force)

    def signal_stop(self):
        """Signal that the worker thread should stop but don't wait.

        This function is useful for stopping multiple threads in parallel when
        combined with wait_stopped().
        """

        self._work_queue.put(STOP_WORKER_ITEM)

    def wait_stopped(self, timeout=None, force=False):
        """Wait for the thread to stop.

        You must have previously called signal_stop or this function will
        hang.

        Args:

            timeout (float): The maximum time to wait for the thread to stop
                before raising a TimeoutExpiredError.  If force is True,
                TimeoutExpiredError is not raised and the thread is just
                marked as a daemon thread so that it does not block cleanly
                exiting the process.
            force (bool): If true and the thread does not exit in timeout seconds
                no error is raised since the thread is marked as daemon and will
                be killed when the process exits.
        """

        self.join(timeout)

        if self.is_alive() and force is False:
            raise TimeoutExpiredError("Error waiting for background thread to exit", timeout=timeout)
