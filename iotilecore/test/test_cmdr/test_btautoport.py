# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import iotile.core.commander.transport
from iotile.core.exceptions import *
import unittest
import os.path
import os
from nose.tools import *
import serial

class testCom:
	""" Fake COM ports """
	def __init__(self, vid=0, pid=0, device=None):
		self.vid = vid
		self.pid = pid
		self.device = device

class testDongle:
	""" Fake cdongle """
	def __init__(self):
		self.stream = testStream()

class testStream:
	""" Fake stream class """
	def stop(self):
		return 0

class TestBTAutoPort(unittest.TestCase):
	"""
	Test to make sure that auto detetion of the bled112 dongle COM port is working
	"""
		
	def testCorrect(self):
		wrongCom = testCom(1234,2,"WRONG")
		rightCom = testCom(9304,1,"RIGHT")
		serial.tools.list_ports.comports = lambda: [wrongCom,rightCom]
		iotile.core.commander.transport.bled112dongle.BLED112Dongle = lambda port: testDongle()
		x = iotile.core.commander.transport.bled112stream.BLED112Stream(None, None, None)

	@raises(HardwareError)
	def testWrong(self):
		wrongCom = testCom(1234,2,"WRONG")
		wrong2Com = testCom(5678,1,"WRONG")
		serial.tools.list_ports.comports = lambda: [wrongCom, wrong2Com]
		x = iotile.core.commander.transport.bled112stream.BLED112Stream(None, None, None)