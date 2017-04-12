"""A thread that can be stopped
"""

import threading
import inspect
import traceback
import time
from iotile.core.exceptions import TimeoutError


class StoppableWorkerThread(threading.Thread):
    """A worker thread that calls a worker function periodically

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
        self._wait = timeout
        self._stop_condition = threading.Event()
        self._running = threading.Event()

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
        """The target routine called to start thread activity
        
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
                        break

                    self._running.set()

                    next(gen)
                    time.sleep(self._wait)
            except StopIteration:
                pass
            except Exception, exc:
                print("Exception occurred in background worker thread")
                traceback.print_exc()
        else:
            try:
                while True:
                    if self._stop_condition.is_set():
                        break

                    self._running.set()

                    self._routine(*self._args, **self._kwargs)
                    time.sleep(self._wait)
            except Exception, exc:
                print("Exception occurred in background worker thread")
                traceback.print_exc()

    def wait_running(self, timeout=None):
        """Wait for the thread to pass control to its routine

        Args:
            timeout (float): The maximum amount of time to wait
        """

        flag = self._running.wait(timeout)

        if flag is False:
            raise TimeoutError("Timeout waiting for thread to start running")

    def stop(self, timeout=None, force=False):
        """Stop the worker thread and synchronously wait for it to finish

        Args:
            timeout (float): The maximum time to wait for the thread to stop
                before raising a TimeoutError.  If force is True, TimeoutError
                is not raised and the thread is just marked as a daemon thread
                so that it does not block cleanly exiting the process.
            force (bool): If true and the thread does not exit in timeout seconds
                no error is raises since the thread is marked as daemon and will
                be killed when the process exits.
        """

        self._stop_condition.set()
        self.join(timeout)

        if self.is_alive() and force is False:
            raise TimeoutError("Error waiting for background thread to exit", timeout=timeout)
