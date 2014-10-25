from externalsim import ExternalSimulator

import subprocess
from pymomo.utilities.typedargs.annotate import *
from pymomo.exceptions import *
from pymomo.utilities.asyncio import AsyncLineBuffer
from collections import namedtuple

#Known Error codes
messages = {
	'Unable to find processor ': '_process_processor_error',
	'the program file type does not contain processor': '_process_no_proc_error',
	'#No such file or directory': '_process_not_found_error',
	'Warning: Logging can\'t be enabled until a cpu has been selected': '_process_no_proc_error'
}

ignored = [
	'you need to specify processor with the processor command',
	'SetProcessorByType FIXME',
	'Extended linear address',
	'Disabling WDT',
	'Leaving pic_processor::LoadProgramFile',
	'running...'

]

InvalidProcessorMessage = namedtuple('InvalidProcessorMessage', ['processor'])
NoProcessorMessage = namedtuple('NoProcessorMessage', [])
NotFoundMessage = namedtuple('NotFoundMessage', ['path'])

def match_message(line, msg):
	if msg[0] == '#':
		msg = msg[1:]
		return msg in line

	return line.startswith(msg)

class GPSIM (ExternalSimulator):
	"""
	A Simworker object encapsulating the gpsim pic12 and pic16 simulator from gputils.
	"""

	prompt = '**gpsim> '
	
	def _sim_path(self):
		return ['gpsim', '-i']

	def _init_sim(self):
		pass

	def _process_message(self, msg, cmd=""):
		if not msg.startswith(cmd):
			raise InternalError("Command was not echoed in simulator response.")

		msg = msg[len(cmd):].rstrip()

		lines = [x for x in msg.split('\n') if len(x) > 0]

		parsed = []

		for line in lines:
			matches = [messages[x] for x in messages.iterkeys() if match_message(line, x)]
			if len(matches) == 0:
				ignore_matched = [x for x in ignored if match_message(line, x)]

				if len(ignore_matched) > 0:
					continue

				raise APIError("Unknown message from gpsim", line=line)
			elif len(matches) > 1:
				raise APIError("Multiple matches for message from gpsim", line=line)

			parser = getattr(self, matches[0])
			parsed.append(parser(line))
		
		return parsed

	def _set_processor(self, proc):
		"""
		Set the processor type for this simulator instance
		"""

		result = self._command('processor', str(proc))
		if len(result) != 0:
			raise InternalError("Error setting processor", msgs=result)


	def set_param(self, name, value):
		"""
		Set the named paramater to the specified value 
		"""

		if name == 'processor':
			self.processor = value
			self._set_processor(value)
		else:
			raise InternalError("Invalid parameter", name=name, value=value)

	def load_program(self, program, type):
		if type == 'elf':
			raise InternalError("ELF files are not supported by gpsim")

		result = self._command('load', program)
		if len(result) != 0:
			raise InternalError("Error loading program", msgs=result)
	
	def execute(self):
		self._command('run', sync=False)
		self.waiting = True

	def raw_command(self, command):
		result = self._command(command)

	def set_log(self, file):
		result = self._command("log on '%s'" % file)
		if len(result) != 0:
			if any(isinstance(x, NoProcessorMessage) for x in result):
				raise InternalError("You must set a processor and load a hex file first")

			raise InternalError("Error adding log", msgs=result)

	#Error code processing logic
	def _process_processor_error(self, line):
		skip = len('Unable to find processor ')
		procname = line[skip:]

		return InvalidProcessorMessage(procname)

	def _process_no_proc_error(self, line):
		return NoProcessorMessage()

	def _process_not_found_error(self, line):
		path,msg = line.rsplit(':')
		if msg != ' No such file or directory':
			raise APIError("Unexpected message processing file not found error", msg=msg, line=line)

		return NotFoundMessage(path)