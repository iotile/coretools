"""A thread that can be stopped
"""

import threading
import inspect
import traceback
import time
from iotile.core.exceptions import TimeoutExpiredError


class StoppableWorkerThread(threading.Thread):
    """A worker thread that calls a worker function periodically.

    This class takes a single callable function and calls that
    function with *args and **kwargs in a loop with a configurable
    delay between each invocation.  There is a public stop() method
    that will kill the thread after the next time the callable function
    returns.

    If you pass a generator function then the function is called in a loop
    with next() until it raises a StopIteration exception at which point
    the thread is closed.  Exceptions thrown from the generator cause the
    thread to exit immediately.  The stop condition of the thread is checked
    every time the generator yields.
    """

    def __init__(self, routine, timeout=0.1, args=None, kwargs=None):
        self._routine = routine
        self._args = args
        self._kwargs = kwargs
        self._stop_condition = threading.Event()
        self._running = threading.Event()

        # In order to keep the thread responsive, we default to checking for our
        # stop signal every 10 milliseconds.  If the execution timeout is less than
        # 10 ms, we use that, otherwise we round it to a multiple of 10 ms
        #
        # Allow the user to specify no wait time if the function we are calling has
        # a built-in delay, like it's reading from a file or some other source of
        # events.
        if timeout is None:
            self._wait = 0.0
            self._wait_count = 0
        elif timeout <= 0.01:
            self._wait = timeout
            self._wait_count = 1
        else:
            self._wait = 0.01
            self._wait_count = int(timeout / self._wait)

        self._generator = inspect.isgeneratorfunction(routine)


        if self._args is None:
            self._args = []

        if self._kwargs is None:
            self._kwargs = {}

        super(StoppableWorkerThread, self).__init__()

        self.daemon = True

    @property
    def generator(self):
        """Whether this thread is running a generator function or not
        """

        return self._generator

    def run(self):
        """The target routine called to start thread activity.

        If the thread is created with a generator function, this iterates
        the generator and checks for a stop condition between each iteration.

        If the thread is created with a normal function, that function is called
        in a loop with the stop condition checked between each invocation.
        """

        if self._generator:
            try:
                gen = self._routine(*self._args, **self._kwargs)

                while True:
                    if self._stop_condition.is_set():
                        return

                    self._running.set()

                    next(gen)

                    for _i in xrange(0, self._wait_count):
                        if self._stop_condition.is_set():
                            return
                        time.sleep(self._wait)

            except StopIteration:
                pass
            except Exception:
                print("Exception occurred in background worker thread")
                traceback.print_exc()
        else:
            try:
                while True:
                    if self._stop_condition.is_set():
                        break

                    self._running.set()

                    self._routine(*self._args, **self._kwargs)

                    # Wait for the desired interval, checking if we should exit
                    for _i in xrange(0, self._wait_count):
                        if self._stop_condition.is_set():
                            return

                        time.sleep(self._wait)
            except Exception:
                print("Exception occurred in background worker thread")
                traceback.print_exc()

    def wait_running(self, timeout=None):
        """Wait for the thread to pass control to its routine.

        Args:
            timeout (float): The maximum amount of time to wait
        """

        flag = self._running.wait(timeout)

        if flag is False:
            raise TimeoutExpiredError("Timeout waiting for thread to start running")

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

        self._stop_condition.set()

    def wait_stopped(self, timeout=None, force=False):
        """Wait for the thread to stop.

        You must have previously called signal_stop or this function will hang.

        Args:
            timeout (float): The maximum time to wait for the thread to stop
                before raising a TimeoutExpiredError.  If force is True, TimeoutExpiredError
                is not raised and the thread is just marked as a daemon thread
                so that it does not block cleanly exiting the process.
            force (bool): If true and the thread does not exit in timeout seconds
                no error is raised since the thread is marked as daemon and will
                be killed when the process exits.
        """

        self.join(timeout)

        if self.is_alive() and force is False:
            raise TimeoutExpiredError("Error waiting for background thread to exit", timeout=timeout)
