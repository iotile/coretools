"""A class that lets you push tasks to a global event loop of the program, letting
your objects create a reference to the asyncio event loop withotu having to
pass a loop everywhere
"""

import asyncio
import logging
import threading


class EventLoop:
    """EventLoop

    A container for the asyncio event loop in a background thread
    """

    loop = None
    thread = None

    _started = False

    _logger = logging.getLogger(__name__)

    @classmethod
    def start(cls):
        """Starts the loop instance if not already created and started"""
        if not cls.loop:
            cls._logger.debug("starting event loop")
            cls.loop = asyncio.new_event_loop()
            cls.thread = threading.Thread(target=cls._loop_thread_main, name="EventLoopThread", daemon=True)
            cls.thread.start()
            cls._started = True

    @classmethod
    def get_loop(cls):
        """Loop getter for users of the event loop object"""
        if not cls.loop:
            cls.start()

        return cls.loop

    @classmethod
    def get_thread(cls):
        """Utility function to get the loop's thread ID for lower-level control/access"""
        return cls.thread

    @classmethod
    def stop_loop_abrupt(cls):
        """Utility function to stop without trying to clean up"""
        if cls.loop and cls.loop.is_running():
            cls.loop.stop()

    @classmethod
    def stop_loop_clean(cls):
        """Proper way to close the event loop that attempts to clean up all tasks"""
        if cls.loop and cls.loop.is_running():
            tasks = asyncio.Task.all_tasks(loop=cls.loop)
            cls.loop.call_soon_threadsafe(cls.loop.create_task, cls._clean_tasks(tasks))
            cls.thread.join()
            cls.loop.stop()

    @classmethod
    def close(cls):
        """Convenience caller to look similar to loop closes"""
        cls.stop_loop_clean()

    @classmethod
    async def _clean_tasks(cls, tasks):
        """Task to clear all other tasks (because the stop_loop_clean
        task errors when it closes itself with this logic)
        """
        remainder = []
        for task in tasks:
            cls._logger.info("Cancelling task %s" % task)
            task.cancel()
            remainder.append(task)
        await asyncio.gather(*remainder, return_exceptions=True)
        cls.loop.stop()

    @classmethod
    def _loop_thread_main(cls):
        """This is the background thread that actually owns the single asyncio event loop that your
        application should be running.
        """
        try:
            cls.loop.run_forever()
        except:
            cls._logger.exception("Exception raised from event loop thread")
        finally:
            cls._logger.debug("stopping loop clean")
            cls.stop_loop_clean()

    @classmethod
    def add_future(cls, fut):
        """Main method by which modules can add futures to the event loop"""
        fut = asyncio.ensure_future(fut, loop=cls.loop)
        cls._logger.debug("future added")
        return fut

    @classmethod
    def add_task(cls, cor):
        """Method by which modules can add tasks to the event loop"""
        tsk = cls.loop.call_soon_threadsafe(cls.loop.create_task, cor)
        cls._logger.debug("task added")
        return tsk
