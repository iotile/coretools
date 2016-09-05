# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

from threading import Thread
from Queue import Queue, Empty
import os
from iotilecore.exceptions import *
import multiprocessing
import signal

class AsyncPacketBuffer:
	def __init__(self, open_function, connstring, header_length, length_function, oob_function=None):
		"""
		Given an underlying file like object, synchronously read from it 
		in a separate thread and communicate the data back to the buffer
		one packet at a time.
		"""

		self.queue = multiprocessing.Queue()
		self.write_queue = multiprocessing.Queue()
		self.oob_queue = multiprocessing.Queue()
		self._stop = multiprocessing.Event()

		#Make sure that we never block the parent proces from quitting
		self.queue.cancel_join_thread()
		self.oob_queue.cancel_join_thread()

		self.process = multiprocessing.Process(target=ReaderMain, args=(connstring, self.queue, self.write_queue, open_function, header_length, length_function, oob_function, self.oob_queue, self._stop))
		self.process.daemon = True
		self.process.start()

	def write(self, value):
		self.write_queue.put(value)

	def stop(self):
		self._stop.set()
		self.process.join()

	def has_packet(self):
		"""
		return True if there is a packet waiting in the queue.
		"""
		
		return not self.queue.empty()

	def read_packet(self, timeout=3.0):
		"""
		read one packet, timeout if one packet is not available in the timeout period
		"""

		try:
			return self.queue.get(timeout=timeout)
		except Empty:
			raise TimeoutError("Timeout waiting for packet in AsyncPacketBuffer")

def WriterThread(queue, file, stop):
	while not stop.is_set():
		try:
			value = queue.get(True, 0.1)
			file.write(value)
		except Empty:
			pass

def ReaderMain(connstring, queue, write_queue, open_function, header_length, length_function, oob_function, oob_queue, stop):
	signal.signal(signal.SIGINT, signal.SIG_IGN)

	file = open_function(connstring)
	stop_flag = False

	with file:
		write_thread = Thread(target=WriterThread, args=(write_queue, file, stop))
		write_thread.start()

		while not stop_flag:
			if stop.is_set():
				break

			header = bytearray()
			while len(header) < header_length:
				chunk = bytearray(file.read(header_length - len(header)))
				header += chunk

				if stop.is_set():
					stop_flag = True
					break

			if stop_flag:
				break
				
			remaining_length = length_function(header)

			remaining = bytearray()
			while len(remaining) < remaining_length:
				chunk = bytearray(file.read(remaining_length - len(remaining)))
				remaining += chunk
				if stop.is_set():
					stop_flag = True
					break

			if stop.is_set():
				break

			#We have a complete packet now, process it
			packet = header + remaining

			#Allow the user to pass a function that flags out of band data and
			#does something special with it immediately
			if oob_function is not None:
				value = oob_function(packet)
				if value is not None:
					oob_queue.put(value)
					continue

			queue.put(packet)

		write_thread.join()