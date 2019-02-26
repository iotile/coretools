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
        if not cls.loop:
            cls.loop = asyncio.new_event_loop()
            cls.thread = threading.Thread(target=cls._loop_thread_main, name="EventLoopThread", daemon=True)
            cls.thread.start()
            cls._started = True


    @classmethod
    def get_loop(cls):
        if not cls.loop:
            cls.start()

        return cls.loop

    @classmethod
    def get_thread(cls):
        return cls.thread


    @classmethod
    def stop_loop_abrupt(cls):
        if cls.loop and cls.loop.is_running():
            cls.loop.stop()

    @classmethod
    def stop_loop_clean(cls):
        if cls.loop and cls.loop.is_running():
            tasks = asyncio.Task.all_tasks(loop=cls.loop)
            cls.loop.call_soon_threadsafe(cls.loop.create_task, cls._clean_tasks(tasks))
            cls.thread.join()
            cls.loop.stop()

    @classmethod
    async def _clean_tasks(cls, tasks):
        remainder = []
        for task in tasks:
            cls._logger.info("Cancelling task %s" % task)
            task.cancel()
            remainder.append(task)
        await asyncio.gather(*remainder, return_exceptions=True)
        cls.loop.stop()


    @classmethod
    def _loop_thread_main(cls):
        print("running event loop foreverrrr")
        try:
            cls.loop.run_forever()
        except:
            cls._logger.exception("Exception raised from event loop thread")
        finally:
            print("stopping loop clean")
            cls.stop_loop_clean()


    @classmethod
    def add_future(cls, fut):
        asyncio.ensure_future(fut, loop=cls.loop)
        print("future secured")

    @classmethod
    def add_task(cls, cor):

        cls.loop.call_soon_threadsafe(cls.loop.create_task, cor)
        print("task added")
