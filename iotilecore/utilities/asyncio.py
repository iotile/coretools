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
		self.process = multiprocessing.Process(target=ReaderMain, args=(connstring, self.queue, self.write_queue, open_function, header_length, length_function, oob_function, self.oob_queue, self._stop))
		self.process.start()

	def write(self, value):
		self.write_queue.put(value)

	def stop(self):
		self._stop.set()
		self.process.join()

	def read_packet(self, timeout=3.0):
		"""
		read one packet, timeout if one packet is not available in the timeout period
		"""

		try:
			return self.queue.get(timeout=timeout)
		except Empty:
			raise TimeoutError("Timeout waiting for packet in AsyncPacketBuffer")

def WriterThread(queue, file, stop, trace):
	while not stop.is_set():
		try:
			value = queue.get(True, 0.1)
			file.write(value)

			if trace is not None:
				import binascii
				trace.write('<<<' + binascii.hexlify(value[:4]) + ' ' + binascii.hexlify(value[4:]) + '\n')
				trace.flush()
		except Empty:
			pass

def ReaderMain(connstring, queue, write_queue, open_function, header_length, length_function, oob_function, oob_queue, stop):
	file = open_function(connstring)
	stop_flag = False

	# FIXME: This is tracing code that should be removed completely once it is no longer needed
	do_trace = False
	if do_trace:
		trace = open("./bled112.txt", "w")
	else:
		trace = None

	with file:
		write_thread = Thread(target=WriterThread, args=(write_queue, file, stop, trace))
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
			
			if trace is not None:
				import binascii
				trace.write('>>>' + binascii.hexlify(header) + ' ')
				trace.flush()
				
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

			if trace is not None:
				trace.write(binascii.hexlify(remaining) + '\n')
				trace.flush()

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
