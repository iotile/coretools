#unit_test12.py

import unit_test
import pic12_unit
import pic12
from pymomo.exceptions import *
from pymomo.gpysim import i2c_log
import os.path
import os

typemap = { 'RS': i2c_log.RepeatedStartCondition, 'S': i2c_log.StartCondition,
			'P': i2c_log.StopCondition, 'A': i2c_log.AddressByte, 'D': i2c_log.DataByte}

class Pic12UnitTest (unit_test.UnitTest):
	def __init__(self, files, **kwargs):
		#Must initialize variables before calling super init b/c they will
		#be overwritten by imported header information.
		self.i2c_capture = None
		self.checkpoints = []
		self.ignore_checkpoints = True
		self.slaves = []
		self.masters = []
		self.mibfile = None
		self.cycle_limit = None
		self.script_additions = {'libraries': set(), 'modules':{}, 'setup_lines': {}, 'sda_node': set(), 'scl_node': set()}
		unit_test.UnitTest.__init__(self, files, **kwargs)

		#Initialize 10K pullups on SDA and SCL to simulate the required pullups on the i2c lines
		self._add_library('libgpsim_modules')
		
		self._add_module('pullup_scl', 'pullup')
		self._add_setupline('pullup_scl', 'pullup_scl.voltage = 5')
		self._add_setupline('pullup_scl', 'pullup_scl.resistance = 10000')
		self._connect_to_scl('pullup_scl.pin')

		self._add_module('pullup_sda', 'pullup')
		self._add_setupline('pullup_sda', 'pullup_sda.voltage = 5')
		self._add_setupline('pullup_sda', 'pullup_sda.resistance = 10000')
		self._connect_to_sda('pullup_sda.pin')

	#PIC12 Specific Attibutes
	def _parse_checkpoints(self, value):
		pts = value.split(',')
		ptlist = [self._add_checkpoint(x) for x in pts]
		self.checkpoints = ptlist

	def _parse_cycle_limit(self, value):
		"""
		Cycle Limit: <number>
		"""
		cycle = int(value.strip(), 0)
		self.cycle_limit = cycle
		self._add_setupline('cycles', 'break c %d' % cycle)

	def _parse_attach_slave(self, value):
		"""
		Attach Slave: <address>, python_module.py

		Create a python slave responder at the given address and attach it to
		the simulation.  Whenever a MIB packet is directed at that address the
		slave responder will process it as if it were attached to the bus.  
		
		Any number of slaves can be attached and they will be named sequentially:
		slave0, slave1, etc. 
		"""

		vals = [x.strip() for x in value.split(',')]
		if len(vals) != 2:
			raise BuildError("Attach slave error: value must be of the form <address>, <python_module.py>", value=value)

		addr, filename = vals

		try:
			addr = int(addr)
		except ValueError:
			raise BuildError("Attach slave error: address must be a number", address=addr)

		filepath = os.path.join(os.path.dirname(self.files[0]), filename)
		if not os.path.exists(filepath):
			raise BuildError("Attach slave error: python module does not exist", filename=filename, cwd=os.getcwd(), filepath=filepath)

		base, ext = os.path.splitext(filename)
		if ext != ".py":
			raise BuildError("Attach slave error: slave responder code must end in .py", filename=filename, extension=ext)

		self.slaves.append((addr, base))
		self.copy_file(filepath, filename)

		#Add this slave into the simulation script
		sname = "slave%d" % len(self.slaves)

		self._add_library('libgpsim_modules')
		self._add_module(sname, 'MoMoPythonSlave')
		self._add_setupline(sname, '%s.address = %d' % (sname, addr))
		self._add_setupline(sname, '%s.logfile = calls_%s.txt' % (sname, sname))
		self._add_setupline(sname, '%s.python_module = %s' % (sname, base))
		self._connect_to_scl('%s.scl' % sname)
		self._connect_to_sda('%s.sda' % sname)

	def _parse_copy(self, value):
		"""
		Copy: src_filename, dst_filename

		Copy the filename into this unit test's output folder so that it can be accessed during
		operation.  Make the result of the unit test depend on this file as well.
		"""

		vals = [x.strip() for x in value.split(',')]
		if len(vals) != 2:
			raise BuildError("Copy error: value must be of the form <src file>, <dest filename>", value=value)

		filename = vals[0]

		filepath = os.path.join(os.path.dirname(self.files[0]), filename)
		if not os.path.exists(filepath):
			raise BuildError("Copy: file does not exist", filename=filename, cwd=os.getcwd(), filepath=filepath)

		self.copy_file(filepath, vals[1])
		self.result_depends(vals[1])

	def _parse_triggered_master(self, value):
		"""
		Triggered Master: cycle, python_file.py

		Attach a master i2c module that begins a transmission cycle
		at the indicated cycle and reads a python file to determine
		the aprropriate packet to send.
		"""

		vals = [x.strip() for x in value.split(',')]
		if len(vals) != 2:
			raise BuildError("Triggered Master: value must be of the form cycle, <python_file.py>", value=value)

		try:
			cycle = int(vals[0])
		except ValueError:
			raise BuildError("Triggered Master: cycle trigger must be a number", cycle=vals[0])

		if cycle <= 0:
			raise BuildError("Triggered Master: cycle trigger must be greater than 0", cycle=vals[0])

		filename = vals[1]

		filepath = os.path.join(os.path.dirname(self.files[0]), filename)
		if not os.path.exists(filepath):
			raise BuildError("Triggered Master: python module does not exist", filename=filename, cwd=os.getcwd(), filepath=filepath)

		base, ext = os.path.splitext(filename)
		if ext != ".py":
			raise BuildError("Triggered Master: master code must end in .py", filename=filename, extension=ext)

		self.copy_file(filepath, filename)

		self.masters.append((cycle, filename))
		sname = "master%d" % len(self.masters)

		#Add this master to the simulation
		self._add_library('libgpsim_modules')
		self._add_module(sname, 'MoMoTriggeredMaster')
		self._add_setupline(sname, '%s.trigger_cycle = %d' % (sname, cycle))
		self._add_setupline(sname, '%s.python_module = %s' % (sname, base))
		self._connect_to_scl('%s.scl' % sname)
		self._connect_to_sda('%s.sda' % sname)

	def _add_library(self, lib):
		"""
		Specify that we need a custom gpsim library
		"""

		self.script_additions['libraries'].add(lib)

	def _add_module(self, name, type):
		"""
		Specify that we need to load a custom gpsim module
		"""

		if name in self.script_additions['modules']:
			raise BuildError("Same GPSIM module name specified twice", name=name, type=type, script_additions=self.script_additions)
		
		self.script_additions['modules'][name] = type

	def _add_setupline(self, name, line):
		"""
		Insert a custom setup line into gpsim script output
		"""

		if name not in self.script_additions['setup_lines']:
			self.script_additions['setup_lines'][name] = []

		self.script_additions['setup_lines'][name].append(line)

	def _connect_to_sda(self, pin):
		self.script_additions['sda_node'].add(pin)

	def _connect_to_scl(self, pin):
		self.script_additions['scl_node'].add(pin)

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

		#Add this module into the test script
		self._add_library('libgpsim_modules')
		self._add_module('record_clock', 'FileRecorder')
		self._add_module('record_data', 'FileRecorder')

		self._add_setupline('record_clock', 'record_clock.digital = true')
		self._add_setupline('record_clock', 'record_clock.file = clock.txt')
		self._add_setupline('record_data', 'record_data.digital = true')
		self._add_setupline('record_data', 'record_data.file = data.txt')

		self._connect_to_scl('record_clock.pin')
		self._connect_to_sda('record_data.pin')

		sigs = [x.strip() for x in value.split(',')]
		self.i2c_capture = [self._process_i2c_signal(x) for x in sigs]
		self.add_intermediate('clock.txt', folder='test')
		self.add_intermediate('data.txt', folder='test')

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
			elif ext == '.mib':
				self.mibfile = os.path.join(self.basedir, f)
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
				passed, observed, obs_short, expected = self._check_i2c_output(chip)
				if passed:
					f.write("I2C Output Match: PASSED\n")
				else:
					f.write("I2C Output Match: FAILED\n")
					f.write("Short output (for copying to test header): %s\n" % obs_short)
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

	def _format_i2c_sequence(self, short=False, error_line=None):
		events = [self._format_event(x, short=short) for x in self.i2c_capture]

		if error_line is not None:
			events[error_line] += " <------ First disagreement"

		if short:
			return ", ".join(events)
		else:
			return "\n".join(events)

	def _format_start(self, ev, short):
		if short:
			return "S"
		else:
			return "Start"

	def _format_repeated_start(self, ev, short):
		if short:
			return "RS"
		else: 
			return "Repeated Start"

	def _format_stop(self, ev, short):
		if short:
			return "P"
		else:
			return "Stop"
	
	def _format_data(self, ev, short):
		a = 'NACK'
		if ev[2]:
			a = 'ACK'	

		if short:
			return "0x%x/%s" % (ev[1], a[0])
		else:
			if ev[1] is None:
				return "XX %s" % a
			else:
				return "0x%x %s" % (ev[1], a)

	def _format_address(self, ev, short):
		a = 'NACK'
		if ev[3]:
			a = 'ACK'

		d = 'READ from'
		if ev[2]:
			d = 'WRITE to'

		if short:
			return "0x%x/%s%s" % (ev[1], d[0], a[0])
		else:
			return "%s 0x%x %s" % (d, ev[1], a)

	def _format_event(self, ev, **kwargs):
		if ev[0] == 'S':
			return self._format_start(ev, **kwargs)
		elif ev[0] == 'P':
			return self._format_stop(ev, **kwargs)
		elif ev[0] == 'D':
			return self._format_data(ev, **kwargs)
		elif ev[0] == 'A':
			return self._format_address(ev, **kwargs)
		elif ev[0] == 'RS':
			return self._format_repeated_start(ev, **kwargs)
		
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
			return False, analyzer.format(), analyzer.format(short=True), self._format_i2c_sequence()

		status = True

		i = 0
		for exp, act in zip(self.i2c_capture, analyzer.bus_events):
			expected_type = typemap[exp[0]]
			if not isinstance(act, expected_type):
				status = False
				break

			if exp[0] == 'D':
				#If we don't care about this data byte, don't match it
				if exp[1] is None and exp[2] == act.acked:
					i += 1
					continue

				if exp[1] != act.value or exp[2] != act.acked:
					status = False
					break

			if exp[0] == 'A':
				if exp[2] != act.is_write or exp[1] != act.address or exp[3] != act.acked:
					status = False
					break

			i+= 1

		error = None
		if status == False:
			error = i

		return status, analyzer.format(), analyzer.format(short=True), self._format_i2c_sequence(error_line=error)

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

			# Allow for specifying bytes that are unpredictable.
			if splitvals[0].lower() == 'xx':
				val = None
			else:
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
