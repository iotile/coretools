"""A global background asyncio event loop for CoreTools.

This class is the base primitive used by all of CoreTools to interact with the
asyncio framework.  There should be a single SharedLoop per process using
CoreTools in an asynchronous fashion.

Various subsystems add tasks to this background event loop which runs until
the process shuts down or until you explicitly stop it using SharedLoop.stop().

The primary mode of interaction with the event loop is by scheduling long
running tasks using SharedLoop.add_task().  You get a BackgroundTask object
back that you can stop at any time from any thread using BackgroundTask.stop().

If you have complex tasks that must be stopped in a specific order, you can
register then as subtasks and their parent task is in charge of stopping
them cleanly in the correct order.
"""

import time
import asyncio
import inspect
import logging
import threading
import atexit
import functools
import concurrent.futures
from iotile.core.exceptions import TimeoutExpiredError, ArgumentError, InternalError, LoopStoppingError


class BackgroundTask:
    """A background coroutine task running in a BackgroundEventLoop.

    This class is a wrapper around asyncio.Task that allows tasks to have
    subtasks.  A subtask is just a regular task but the parent task is in
    charge of stopping it when required.  This distinction allows you to
    create hierarchies of tasks that can be cleanly stopped in a known
    order when the BackgroundEventLoop is stopped.

    Tasks can also be given names that will be logged for debugging purposes.

    This class should never be created directly but will be returned
    by BackgroundEventLoop.add_task().

    Generally, you always want to start a task with a coroutine that it
    runs.  However, there are cases where you just want a "parent" task
    as a placeholder that can group various subtasks that do have coroutines.

    In that case, you can pass ``cor`` as None to say that there is no
    underlying asnycio task backing this task.  In that case, you **should**
    pass ``finalizer`` as something other than None.  You can create a task
    that has no coroutine and no finalizer, which is basically just a
    placeholder that does nothing.

    Args:
        cor (coroutine or asyncio.Task): An asyncio Task or the coroutine
            that we should execute as a task.  If a coroutine is given
            it is scheduled as a task in threadsafe manner automatically.
        name (str): The name of the task for pretty printing and debug
            purposes.  If not specified, it defaults to the underlying
            asyncio task object instance name.
        finalizer (callable): An optional callable that should be
            invoked to cancel the task.  If specified it will be called
            with a single argument, this BackgroundTask instance.

            If not specified, calling stop() will result in cancel()
            being called on the underlying task.

            The finalizer (or task.cancel()) is always invoked inside
            the event loop.  If finalizer is a coroutine it is awaited.
        loop (BackgroundEventLoop): The background event loop this task
            should run in.  If not specified, it defaults to the global
            SharedLoop instance.
        stop_timeout (float): The maximum amount of time to wait for this
            task to stop when stop() is called in seconds.  None indicates
            an unlimited amount of time.  Default is 1 second.
    """

    #pylint:disable=too-many-arguments;This class is not meant to be directly constructed by the user
    def __init__(self, cor, name=None, finalizer=None, stop_timeout=1.0, loop=None):
        self._name = name
        self._finalizer = finalizer
        self._stop_timeout = stop_timeout
        self._logger = logging.getLogger(__name__)
        self.stopped = False

        if loop is None:
            loop = SharedLoop

        if not isinstance(loop, BackgroundEventLoop):
            raise ArgumentError("A BackgroundTask must be created with a BackgroundEventLoop, loop={}".format(loop))

        self._loop = loop

        self.subtasks = []
        if inspect.iscoroutine(cor):
            self.task = _create_task_threadsafe(cor, self._loop)
        elif inspect.iscoroutinefunction(cor):
            self.task = _create_task_threadsafe(cor(), self._loop)
        elif isinstance(cor, asyncio.Task):
            self.task = cor
        elif cor is None:
            self.task = None
        else:
            raise ArgumentError("Unknown object passed to Background task: {}".format(cor))

    @property
    def name(self):
        """A descriptive name for this task."""

        if self._name is not None:
            return self._name

        return str(self.task)

    def create_subtask(self, cor, name=None, stop_timeout=1.0):
        """Create and add a subtask from a coroutine.

        This function will create a BackgroundTask and then
        call self.add_subtask() on it.

        Args:
            cor (coroutine): The coroutine that should be wrapped
                in a background task.
            name (str): An optional name for the task.
            stop_timeout (float): The maximum time to wait for this
                subtask to die after stopping it.

        Returns:
            Backgroundtask: The created subtask.
        """

        if self.stopped:
            raise InternalError("Cannot add a subtask to a parent that is already stopped")

        subtask = BackgroundTask(cor, name, loop=self._loop, stop_timeout=stop_timeout)
        self.add_subtask(subtask)
        return subtask

    def add_subtask(self, subtask):
        """Link a subtask to this parent task.

        This will cause stop() to block until the subtask has also
        finished.  Calling stop will not directly cancel the subtask.
        It is expected that your finalizer for this parent task will
        cancel or otherwise stop the subtask.

        Args:
            subtask (BackgroundTask): Another task that will be stopped
                when this task is stopped.
        """

        if self.stopped:
            raise InternalError("Cannot add a subtask to a parent that is already stopped")

        if not isinstance(subtask, BackgroundTask):
            raise ArgumentError("Subtasks must inherit from BackgroundTask, task={}".format(subtask))

        #pylint:disable=protected-access;It is the same class as us so is equivalent to self access.
        if subtask._loop != self._loop:
            raise ArgumentError("Subtasks must run in the same BackgroundEventLoop as their parent",
                                subtask=subtask, parent=self)

        self.subtasks.append(subtask)

    async def stop(self):
        """Stop this task and wait until it and all its subtasks end.

        This function will finalize this task either by using the finalizer
        function passed during creation or by calling task.cancel() if no
        finalizer was passed.

        It will then call join() on this task and any registered subtasks
        with the given maximum timeout, raising asyncio.TimeoutError if
        the tasks did not exit within the given timeout.

        This method should only be called once.

        After this method returns, the task is finished and no more subtasks
        can be added.  If this task is being tracked inside of the
        BackgroundEventLoop that it is part of, it will automatically be
        removed from the event loop's list of tasks.
        """

        if self.stopped:
            return

        self._logger.debug("Stopping task %s", self.name)

        if self._finalizer is not None:
            try:
                result = self._finalizer(self)
                if inspect.isawaitable(result):
                    await result
            except:  #pylint:disable=bare-except;We need to make sure we always wait for the task
                self._logger.exception("Error running finalizer for task %s",
                                       self.name)
        elif self.task is not None:
            self.task.cancel()

        tasks = []
        if self.task is not None:
            tasks.append(self.task)

        tasks.extend(x.task for x in self.subtasks)
        finished = asyncio.gather(*tasks, return_exceptions=True)
        outcomes = []

        try:
            outcomes = await asyncio.wait_for(finished, timeout=self._stop_timeout)
        except asyncio.TimeoutError as err:
            # See discussion here: https://github.com/python/asyncio/issues/253#issuecomment-120138132
            # This prevents a nuisance log error message, finished is guaranteed
            # to be cancelled but not awaited when wait_for() has a timeout.
            try:
                outcomes = await finished
            except asyncio.CancelledError:
                pass

            # See https://mail.python.org/pipermail/python-3000/2008-May/013740.html
            # for why we need to explictly name the error here
            raise err
        finally:
            self.stopped = True
            for outcome in outcomes:
                if isinstance(outcome, Exception) and not isinstance(outcome, asyncio.CancelledError):
                    self._logger.error(outcome)

            if self in self._loop.tasks:
                self._loop.tasks.remove(self)

    def stop_threadsafe(self):
        """Stop this task from another thread and wait for it to finish.

        This method must not be called from within the BackgroundEventLoop but
        will inject self.stop() into the event loop and block until it
        returns.

        Raises:
            TimeoutExpiredError: If the task does not stop in the given
                timeout specified in __init__()
        """

        if self.stopped:
            return

        try:
            self._loop.run_coroutine(self.stop())
        except asyncio.TimeoutError:
            raise TimeoutExpiredError("Timeout stopping task {} with {} subtasks".format(self.name, len(self.subtasks)))


class BackgroundEventLoop:
    """A shared asyncio event loop running in a background thread.

    This class represents a single background event loop.

    The background thread is created the first time a request is made that
    requires a loop to present so it is cheap to create a BackgroundEventLoop
    and not use it in any way.

    There is also a global instance of BackgroundEventLoop called SharedLoop
    that can be used when you just want to add tasks to a single shared loop.
    Creating your own BackgroundEventLoop should not be generally done unless
    you are unit testing.

    A background event loop cannot be restarted once it stops.  Once the shutdown
    process is started by calling ``stop()``, no more tasks can be added to the
    loop and attempts to add them will raise an InternalError.

    This prevents people from accidentally adding more tasks while the loop is
    shutting down.
    """

    def __init__(self):
        self.loop = None
        self.thread = None
        self.stopping = False
        self.tasks = set()

        self._logger = logging.getLogger(__name__)
        self._loop_check = threading.local()
        self._pool = None

    def start(self, aug='EventLoopThread'):
        """Ensure the background loop is running.

        This method is safe to call multiple times.  If the loop is already
        running, it will not do anything.
        """

        if self.stopping:
            raise LoopStoppingError("Cannot perform action while loop is stopping.")

        if not self.loop:
            self._logger.debug("Starting event loop")
            self.loop = asyncio.new_event_loop()
            self.thread = threading.Thread(target=self._loop_thread_main, name=aug, daemon=True)
            self.thread.start()

    def wait_for_interrupt(self, check_interval=1.0, max_time=None):
        """Run the event loop until we receive a ctrl-c interrupt or max_time passes.

        This method will wake up every 1 second by default to check for any
        interrupt signals or if the maximum runtime has expired.  This can be
        set lower for testing purpose to reduce latency but in production
        settings, this can cause increased CPU usage so 1 second is an
        appropriate value.

        Args:
            check_interval (float): How often to wake up and check for
                a SIGTERM. Defaults to 1s.  Setting this faster is useful
                for unit testing.  Cannot be < 0.01 s.
            max_time (float): Stop the event loop after max_time seconds.
                This is useful for testing purposes.  Defaults to None,
                which means run forever until interrupt.
        """

        self.start()

        wait = max(check_interval, 0.01)
        accum = 0

        try:
            while max_time is None or accum < max_time:
                try:
                    time.sleep(wait)
                except IOError:
                    pass  # IOError comes when this call is interrupted in a signal handler

                accum += wait
        except KeyboardInterrupt:
            pass

    def stop(self):
        """Synchronously stop the background loop from outside.

        This method will block until the background loop is completely stopped
        so it cannot be called from inside the loop itself.

        This method is safe to call multiple times.  If the loop is not
        currently running it will return without doing anything.
        """

        if not self.loop:
            return

        if self.inside_loop():
            raise InternalError("BackgroundEventLoop.stop() called from inside event loop; "
                                "would have deadlocked.")

        try:
            self.run_coroutine(self._stop_internal())
            self.thread.join()

            if self._pool is not None:
                self._pool.shutdown(wait=True)
        except:
            self._logger.exception("Error stopping BackgroundEventLoop")
            raise
        finally:
            self.thread = None
            self.loop = None
            self._pool = None
            self.tasks = set()

    def get_loop(self):
        """Get the current loop instance.

        If there is no current loop, a new loop is created and started before
        returning.

        Returns:
            asyncio.Loop: The loop.
        """

        if not self.loop:
            self.start()

        return self.loop

    def inside_loop(self):
        """Check if we are running inside the event loop.

        This can be used to decide whether we need to use a threadsafe method
        to interact with the loop or whether we can just interact with it
        directly. It is used inside BackgroundEventLoop to check for situations that
        would deadlock and raise an Exception instead.

        Returns:
            bool: True if we are running inside the loop thread.
        """

        return self._loop_check.__dict__.get('inside_loop', False)

    async def _stop_internal(self):
        """Cleanly stop the event loop after shutting down all tasks."""

        # Make sure we only try to stop once
        if self.stopping is True:
            return

        self.stopping = True

        awaitables = [task.stop() for task in self.tasks]
        results = await asyncio.gather(*awaitables, return_exceptions=True)
        for task, result in zip(self.tasks, results):
            if isinstance(result, Exception):
                self._logger.error("Error stopping task %s: %s", task.name, repr(result))

        # It is important to defer this call by one loop cycle so
        # that this coroutine is finalized and anyone blocking on it
        # resumes execution.
        self.loop.call_soon(self.loop.stop)

    def _loop_thread_main(self):
        """Main background thread running the event loop."""

        asyncio.set_event_loop(self.loop)
        self._loop_check.inside_loop = True

        try:
            self._logger.debug("Starting loop in background thread")
            self.loop.run_forever()
            self._logger.debug("Finished loop in background thread")
        except:  # pylint:disable=bare-except;This is a background worker thread.
            self._logger.exception("Exception raised from event loop thread")
        finally:
            self.loop.close()

    # pylint:disable=too-many-arguments;These all have sane defaults that should not be changed often.
    def add_task(self, cor, name=None, finalizer=None, stop_timeout=1.0, parent=None):
        """Schedule a task to run on the background event loop.

        This method will start the given coroutine as a task and  keep track
        of it so that it can be properly shutdown which the event loop is
        stopped.

        If parent is None, the task will be stopped by calling finalizer()
        inside the event loop and then awaiting the task.  If finalizer is
        None then task.cancel() will be called to stop the task.  If finalizer
        is specified, it is called with a single argument (self, this
        BackgroundTask).  Finalizer can be a simple function, or any
        awaitable.  If it is an awaitable it will be awaited.

        If parent is not None, it must be a BackgroundTask object previously
        created by a call to BackgroundEventLoop.add_task() and this task will be
        registered as a subtask of that task.  It is that task's job then to
        cancel this task or otherwise stop it when it is stopped.

        This method is safe to call either from inside the event loop itself
        or from any other thread without fear of deadlock or race.

        Args:
            cor (coroutine or asyncio.Task): An asyncio Task or the coroutine
                that we should execute as a task.  If a coroutine is given
                it is scheduled as a task in threadsafe manner automatically.
            name (str): The name of the task for pretty printing and debug
                purposes.  If not specified, it defaults to the underlying
                asyncio task object instance name.
            finalizer (callable): An optional callable that should be
                invoked to cancel the task.  If not specified, calling stop()
                will result in cancel() being called on the underlying task.


            stop_timeout (float): The maximum amount of time to wait for this
                task to stop when stop() is called in seconds.  None indicates
                an unlimited amount of time.  Default is 1.

                This is ignored if parent is not None.
            parent (BackgroundTask): A previously created task that will take
                responsibility for stopping this task when it is stopped.

        Returns:
            BackgroundTask: The BackgroundTask representing this task.
        """

        if self.stopping:
            raise LoopStoppingError("Cannot add task because loop is stopping")

        # Ensure the loop exists and is started
        self.start()

        if parent is not None and parent not in self.tasks:
            raise ArgumentError("Designated parent task {} is not registered".format(parent))

        task = BackgroundTask(cor, name, finalizer, stop_timeout, loop=self)
        if parent is None:
            self.tasks.add(task)
            self._logger.debug("Added primary task %s", task.name)
        else:
            parent.add_subtask(task)
            self._logger.debug("Added subtask %s to parent %s", task.name, parent.name)

        return task

    def run_coroutine(self, cor, *args, **kwargs):
        """Run a coroutine to completion and return its result.

        This method may only be called outside of the event loop.
        Attempting to call it from inside the event loop would deadlock
        and will raise InternalError instead.

        Args:
            cor (coroutine): The coroutine that we wish to run in the
                background and wait until it finishes.

        Returns:
            object: Whatever the coroutine cor returns.
        """

        if self.stopping:
            raise LoopStoppingError("Could not launch coroutine because loop is shutting down: %s" % cor)

        self.start()

        cor = _instaniate_coroutine(cor, args, kwargs)

        if self.inside_loop():
            raise InternalError("BackgroundEventLoop.run_coroutine called from inside event loop, "
                                "would have deadlocked.")

        future = self.launch_coroutine(cor)
        return future.result()

    def launch_coroutine(self, cor, *args, **kwargs):
        """Start a coroutine task and return a blockable/awaitable object.

        If this method is called from inside the event loop, it will return an
        awaitable object.  If it is called from outside the event loop it will
        return an concurrent Future object that can block the calling thread
        until the operation is finished.

        Args:
            cor (coroutine): The coroutine that we wish to run in the
                background and wait until it finishes.

        Returns:
            Future or asyncio.Task: A future representing the coroutine.

            If this method is called from within the background loop
            then an awaitable asyncio.Tasks is returned.  Otherwise,
            a concurrent Future object is returned that you can call
            ``result()`` on to block the calling thread.
        """

        if self.stopping:
            raise LoopStoppingError("Could not launch coroutine because loop is shutting down: %s" % cor)

        # Ensure the loop exists and is started
        self.start()

        cor = _instaniate_coroutine(cor, args, kwargs)

        if self.inside_loop():
            return asyncio.ensure_future(cor, loop=self.loop)

        return asyncio.run_coroutine_threadsafe(cor, loop=self.loop)

    def run_in_executor(self, func, *args, **kwargs):
        """Execute a function on a background executor.

        This method is used to run blocking functions in an awaitable fashion.
        The function is dispatched to a background worker thread and an
        awaitable is returned that will finalize when the function has
        finished.
        """

        self.start()

        if self._pool is None:
            self._pool = concurrent.futures.ThreadPoolExecutor()

        return self.loop.run_in_executor(self._pool, functools.partial(func, *args, **kwargs))

    def log_coroutine(self, cor, *args, **kwargs):
        """Run a coroutine logging any exception raised.

        This routine will not block until the coroutine is finished
        nor will it return any result.  It will just log if any
        exception is raised by the coroutine during operation.

        It is safe to call from both inside and outside the event loop.

        There is no guarantee on how soon the coroutine will be scheduled.

        Args:
            cor (coroutine): The coroutine that we wish to run in the
                background and wait until it finishes.
        """

        if self.stopping:
            raise LoopStoppingError("Could not launch coroutine because loop is shutting down: %s" % cor)

        self.start()

        cor = _instaniate_coroutine(cor, args, kwargs)

        def _run_and_log():
            task = self.loop.create_task(cor)
            task.add_done_callback(lambda x: _log_future_exception(x, self._logger))

        if self.inside_loop():
            _run_and_log()
        else:
            self.loop.call_soon_threadsafe(_run_and_log)

    def create_event(self):
        """Attach an Event to the background loop.

        Returns:
            asyncio.Event
        """

        self.start()
        return asyncio.Event(loop=self.loop)

    def create_lock(self):
        """Attach a Lock to the background loop.

        Returns:
            asyncio.Lock
        """

        self.start()
        return asyncio.Lock(loop=self.loop)

    def create_future(self):
        """Attach a Future to the background loop.

        Returns:
            asyncio.Future
        """

        self.start()
        return asyncio.Future(loop=self.loop)

    def create_queue(self):
        """Attach a Queue to the background loop.

        Returns:
            asyncio.Queue
        """

        self.start()
        return asyncio.Queue(loop=self.loop)


def _create_task_threadsafe(cor, loop):
    asyncio_loop = loop.get_loop()

    if loop.inside_loop():
        return asyncio_loop.create_task(cor)

    async def _task_creator():
        return asyncio_loop.create_task(cor)

    future = asyncio.run_coroutine_threadsafe(_task_creator(), loop=asyncio_loop)
    return future.result()


def _instaniate_coroutine(cor, args, kwargs):
    if inspect.iscoroutinefunction(cor):
        cor = cor(*args, **kwargs)
    elif len(args) > 0 or len(kwargs) > 0:
        raise ArgumentError("You cannot pass arguments if coroutine is already created", args=args, kwargs=kwargs)

    return cor


def _log_future_exception(future, logger):
    """Log any exception raised by future."""

    if not future.done():
        return

    try:
        future.result()
    except:  #pylint:disable=bare-except;This is a background logging helper
        logger.warning("Exception in ignored future: %s", future, exc_info=True)


# Create a single global event loop that anyone can add tasks to.
SharedLoop = BackgroundEventLoop()  # pylint:disable=invalid-name;This is for backwards compatibility.

# Ensure that the concurrent atexit handler is registered before our atexit handler.
#
# If we register a task that uses the concurrent API to run things on executor
# threads, those threads need to be still running when we stop the event loop
# atexit in case they are used during the shutdown process.
#
# The order of atexit handlers is the opposite of the order in which they are
# registered, so ensure the thread handler gets registered first.
#
# See: https://github.com/python/cpython/blob/master/Lib/concurrent/futures/thread.py#L33

# pylint:disable=wrong-import-position,wrong-import-order,unused-import;See above comment
import concurrent.futures.thread
atexit.register(SharedLoop.stop)
