from pymomo.commander.exceptions import *
from pymomo.exceptions import *
import struct

class SensorStream:
	InputBit = (1<<11)
	NodeBit = (1<<12)
	UnbufferedBit = (1<<13)
	CounterBit = (1<<14)
	ConstantBit = (1<<15)

	FlagsMask = (0b11111 << 11)

	def __init__(self, desc):
		"""
		Create a sensor stream from either a string descriptor or a numeric ID

		sensor stream names are 16 bit unsigned integers with 8 bits of ID number
		and other flag bits that specify how and where the stream is stored.
		"""

		if isinstance(desc, basestring):
			self.id = self._process_descriptor(desc)
		elif isinstance(desc, int):
			self.id = desc
		else:
			raise ValidationError("Could not convert sensor stream descriptor to integer", descriptor=desc)

		self.buffered = False
		self.output = False

		#Set some useful flags so we know where to look for this stream
		if not (self.id & SensorStream.UnbufferedBit):
			self.buffered = True

			short_id = self.id & (~SensorStream.FlagsMask)
			if short_id >= 128 and short_id < 255 and not (self.id & SensorStream.NodeBit):
				self.output = True

	def _process_descriptor(self, desc):
		"""
		Process a string descriptor into a numeric sensor stream id

		String format is:
		[input|output|buffered node|unbuffered node|constant|counter] (number)
		"""

		typemap = {	'input': (SensorStream.InputBit | SensorStream.UnbufferedBit), 'output': 0, 'buffered node': (SensorStream.NodeBit), 
					'unbuffered node': (SensorStream.NodeBit | SensorStream.UnbufferedBit), 'constant': (SensorStream.UnbufferedBit | SensorStream.ConstantBit),
					'counter': (SensorStream.UnbufferedBit | SensorStream.CounterBit) }

		typename,sep,idnumber = desc.rpartition(' ')

		if typename not in typemap:
			raise ValidationError("Unknown stream type", typename=typename, known_types=typemap.keys(), descriptor=desc)

		try:
			idnumber = int(idnumber, 0)
		except ValueError:
			raise ValidationError("Could not convert stream id to a number", id_number = idnumber, descriptor=desc)

		#TODO: Verify that the stream ids are in the appropriate range for each type of input/output/intermediate stream type
		return idnumber | typemap[typename] 

def size():
	return 2

def convert(arg):
	if isinstance(arg, SensorStream):
		return arg

	return SensorStream(arg)

#Formatting Functions
def default_formatter(arg, **kwargs):
	return str(arg.id)

#Validator Function
def validate_buffered(arg, **kwargs):
	if arg.id & SensorStream.UnbufferedBit:
		raise ValueError("Stream is not buffered")