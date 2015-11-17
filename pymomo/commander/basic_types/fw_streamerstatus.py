from pymomo.commander.exceptions import *
from pymomo.exceptions import *
import struct
import datetime

class StreamerStatus:
	"""

	"""

	def __init__(self, binvalue):
		last_attempt, last_success, last_status, last_error, attempt, comm = struct.unpack("<LLBBBB", binvalue)

		timebase = datetime.datetime(2000, 1, 1)
		attempt_delta = datetime.timedelta(seconds=last_attempt)
		success_delta = datetime.timedelta(seconds=last_success)

		self.last_attempt = timebase + attempt_delta
		self.last_success = timebase + success_delta
		self.last_status = last_status
		self.last_error = last_error
		self.attempt_num = attempt
		self.comm_status = comm

	def __str__(self):
		output  = ""
		output += "SensorGraph Streamer\n"
		output += "Last successful stream: %s\n" % self.last_success.isoformat()
		output += "Last streaming attempt: %s\n" % self.last_attempt.isoformat()
		output += "Last streaming result: %d\n" % self.last_status
		output += "Last streaming error: %d\n" % self.last_error
		output += "Backoff attempt number: %d\n" % self.attempt_num
		output += "Current CommStream state: %d" % self.comm_status

		return output


def size():
	return 12

def convert(arg):
	if isinstance(arg, StreamerStatus):
		return arg

	raise ValueError("fw_streamerstatus can only be created from binary data inside a bytearray")

def convert_binary(arg, **kwargs):
	return StreamerStatus(arg)

#Formatting Functions
def default_formatter(arg, **kwargs):
	return str(arg)