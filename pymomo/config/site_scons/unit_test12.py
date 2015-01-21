#unit_test12.py

import unit_test
import pic12_unit
from pymomo.exceptions import *
from pymomo.gpysim import i2c_log
import os.path

typemap = { 'RS': i2c_log.RepeatedStartCondition, 'S': i2c_log.StartCondition,
			'P': i2c_log.StopCondition, 'A': i2c_log.AddressByte, 'D': i2c_log.DataByte}

class Pic12UnitTest (unit_test.UnitTest):
	def __init__(self, files, **kwargs):
		#Must initialize variables before calling super init b/c they will
		#be overwritten by imported header information.
		self.i2c_capture = None
		self.checkpoints = []
		unit_test.UnitTest.__init__(self, files, **kwargs)

	#PIC12 Specific Attibutes
	def _parse_checkpoints(self, value):
		pts = value.split(',')
		ptlist = [self._add_checkpoint(x) for x in pts]
		self.checkpoints = ptlist

	def _parse_i2c_capture(self, value):
		"""
		I2C Capture: <sequence> allows unit tests to specify what I2C signals must 
		be transmitted exactly in order for the test to pass.  It is in the form of
		<signal 1>[, <signal 2>, ...]
		where signal is one of the following:
		S, RS, P, number/[A|N], address/[R|W][A|N]
		S, RS and P correspond with start, repeated start and stop conditions.
		number should be an 8-bit integer literal in decimal or prefixed hex or
		binary.
		address should be a 7-bit literal with R or W corresponding to read or
		write indication.
		For numbers and addresses, A corresponds to the acknowledge bit being set
		and N corresponds to it being cleared.
		"""

		sigs = [x.strip() for x in value.split(',')]
		self.i2c_capture = [self._process_i2c_signal(x) for x in sigs]
		self.add_intermediate('clock.txt', folder='test')
		self.add_intermediate('data.txt', folder='test')

	def _process_i2c_signal(self, sig):
		if sig.upper() == 'S':
			return ('S', None)
		elif sig.upper() == 'RS':
			return ('RS', None)
		elif sig.upper() == 'P':
			return ('P', None)
		else:
			#sig should be a number
			splitvals = sig.split('/')
			if len(splitvals) != 2:
				raise BuildError("No modifier specified in data byte", test=self.name, value=sig)

			val = int(splitvals[0],0)
			mods = splitvals[1].upper()

			if len(mods) == 0 or len(mods) > 2:
				raise BuildError("Modifier too long or missing in I2C capture data byte specification", test=self.name, value=sig, parsed_modifier=mods)

			if mods[-1] != 'A' and mods[-1] != 'N':
				raise BuildError("Invalid A/N modifier in I2C capture data or address specification", test=self.name, value=sig, parsed_modifier=mods)

			if len(mods) == 2 and mods[0] != 'R' and mods[0] != 'W':
				raise BuildError("Invalid R/W modifier in I2C capture address byte specification", test=self.name, value=sig, parsed_modifier=mods)

			#Parse a data byte
			if len(mods) == 1:
				return ('D', val, mods[0] == 'A')
			else:
				return ('A', val, mods[0] == 'W', mods[1] == 'A')

	def _parse_additional(self, value):
		"""
		Parse an Additional:<file1>,<fileN>
		header line, taking the appropriate action
		"""

		parsed = value.split(',')
		files = map(lambda x: x.rstrip().lstrip(), parsed)

		for f in files:
			base, ext = os.path.splitext(f)

			if ext == '.as':
				self.files += (os.path.join(self.basedir, f), )
			elif ext == '.cmd':
				self.cmdfile = os.path.join(self.basedir, f)
			else:
				raise BuildError("Unknown file extension in Additional header", test=self.name, filename=f)

	def _parse_target(self, target):
		return target

	def build_target(self, target, summary_env):
		cmdfile = None

		if hasattr(self, 'cmdfile'):
			cmdfile = self.find_support_file(self.cmdfile, target)
		
		pic12_unit.build_unittest(self, target, summary_env, cmds=cmdfile)

	def check_output(self, chip, log):
		with open(log, 'a') as f:
			f.write('\n## Additional Tests ##\n')

			if self.i2c_capture is not None:
				passed, observed, expected = self._check_i2c_output(chip)
				if passed:
					f.write("I2C Output Match: PASSED\n")
				else:
					f.write("I2C Output Match: FAILED\n")
					f.write("# Observed Output #\n")
					f.write(observed)
					if observed[-1] != '\n':
						f.write('\n')
					f.write("# Expected Output #\n")
					f.write(expected)
					if expected[-1] != '\n':
						f.write('\n')

					return passed

		return True

	def _format_i2c_sequence(self):
		events = [self._format_event(x) for x in self.i2c_capture]
		return "\n".join(events)

	def _format_start(self, ev):
		return "Start"

	def _format_repeated_start(self, ev):
		return "Repeated Start"

	def _format_stop(self, ev):
		return "Stop"
	
	def _format_data(self, ev):
		a = 'NACK'
		if ev[2]:
			a = 'ACK'

		return "0x%x %s" % (ev[1], a)

	def _format_address(self, ev):
		a = 'NACK'
		if ev[3]:
			a = 'ACK'

		d = 'READ from'
		if ev[2]:
			d = 'WRITE to'

		return "%s 0x%x %s" % (d, ev[1], a)

	def _format_event(self, ev):
		if ev[0] == 'S':
			return self._format_start(ev)
		elif ev[0] == 'P':
			return self._format_stop(ev)
		elif ev[0] == 'D':
			return self._format_data(ev)
		elif ev[0] == 'A':
			return self._format_address(ev)
		elif ev[0] == 'RS':
			return self._format_repeated_start(ev)
		
		raise InternalError("Unknown event type in i2c log, cannot format", event=ev)

	def _check_i2c_output(self, chip):
		"""
		Verify that the unit test's expected i2c output actually matches what is output during
		the simulation.
		"""

		folder = self.build_dirs(chip)['test']
		datapath = os.path.join(folder, 'data.txt')
		clockpath = os.path.join(folder, 'clock.txt')

		analyzer = i2c_log.I2CAnalyzer.FromGPSIMLogs(clockpath, datapath)

		if len(analyzer.bus_events) != len(self.i2c_capture):
			return False, analyzer.format(), self._format_i2c_sequence()

		status = True

		for exp, act in zip(self.i2c_capture, analyzer.bus_events):
			expected_type = typemap[exp[0]]
			if not isinstance(act, expected_type):
				status = False
				break

			if exp[0] == 'D':
				if exp[1] != act.value or exp[2] != act.acked:
					status = False
					break

			if exp[0] == 'A':
				if exp[2] != act.is_write or exp[1] != act.address or exp[3] != act.acked:
					status = False
					break

		return status, analyzer.format(), self._format_i2c_sequence()


	def _add_checkpoint(self, pt):
		"""
		Given a checkpoint of the form symbol=value or symbol, parse the symbol and
		value.  If no value is given, value=0 is assumed
		"""

		if '=' in pt:
			symbol, val = pt.split('=')
			symbol = symbol.strip()
			val = val.strip()
			val = int(val,0)
			return symbol, val
		
		return pt.strip(), 0

unit_test.known_types['executive'] = Pic12UnitTest
unit_test.known_types['application'] = Pic12UnitTest
unit_test.known_types['executive_integration'] = Pic12UnitTest
