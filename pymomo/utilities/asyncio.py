#A threaded implementaton of asyncronous line oriented
#IO.  This allows a python to program to read from a
#pipe that is not seekable or peekable in a cross-platform
#way without potentially blocking forever.

from threading import Thread, Event, Condition
from Queue import Queue
import os
from pymomo.exceptions import *
import sys

class AsyncLineBuffer:
	def __init__(self, file, separator='\n', strip=True):
		"""
		Given an underlying file like object, syncronously read from it 
		in a separate thread and communicate the data back to the buffer
		one byte at a time.
		"""

		self.queue = Queue()
		self.items = Condition()
		self.thread = Thread(target=AsyncLineBuffer.ReaderThread, args=(self.queue, file, self.items, separator, strip))
		self.thread.daemon = True
		self.thread.start()

	@staticmethod
	def ReaderThread(queue, file, items, separator, strip):
		while True:
			line_done = False
			line = ''
			while not line_done:
				c = file.read(1)
				line += c

				if line.endswith(separator):
					line_done = True

			if strip:
				line = line[:-len(separator)]

			items.acquire()
			queue.put(line)
			items.notify()
			items.release()

	def available(self):
		"""
		Return the number of available lines in the buffer
		"""
		
		return self.queue.qsize()

	def readline(self, timeout=3.0):
		"""
		read one line, timeout if one line is not available in the timeout period
		"""

		self.items.acquire()
		if self.available() == 0:
			self.items.wait(timeout)
			if self.available() == 0:
				self.items.release()
				raise TimeoutError("Asynchronous Read timed out waiting for a line to be read")

			self.items.release()

		return self.queue.get()
