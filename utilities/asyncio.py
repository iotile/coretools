#A threaded implementaton of asyncronous line oriented
#IO.  This allows a python to program to read from a
#pipe that is not seekable or peekable in a cross-platform
#way without potentially blocking forever.

from threading import Thread, Event
from cStringIO import StringIO
from Queue import Queue
import os
from pymomo.utilities.typedargs.exceptions import *

class AsyncLineBuffer:
	def __init__(self, file):
		"""
		Given an underlying file like object, syncronously read from it 
		in a separate thread and communicate the data back to the buffer
		one byte at a time.
		"""

		self.queue = Queue()
		self.items = Event()
		self.thread = Thread(target=AsyncLineBuffer.ReaderThread, args=(self.queue, file, self.items))
		self.thread.daemon = True
		self.thread.start()
		self.buffer = StringIO()

	@staticmethod
	def ReaderThread(queue, file, items):
		while True:
			c = file.read(1)
			queue.put(c)
			items.set()

	def _update_buffer(self):
		"""
		Add all current contents that have been read to the buffer
		without moving the current position.
		"""

		loc = self.buffer.tell()

		while not self.queue.empty():
			self.buffer.write(self.queue.get())

		self.buffer.seek(loc)

	def available(self):
		"""
		Return the number of available bytes in the buffer
		"""
		loc = self.buffer.tell()
		self.buffer.seek(0, os.SEEK_END)
		end = self.buffer.tell()
		self.buffer.seek(loc)

		return end-loc

	def read(self, n, timeout=3.0):
		"""
		read n bytes, timeout if n bytes are not available 
		"""

		while self.available() < n:
			flag_set = self.items.wait(timeout)
			if flag_set is False:
				raise TimeoutError("Asynchronous Read timed out waiting for %d bytes" % n)

			self.items.clear()
			self._update_buffer()

		return self.buffer.read(n)