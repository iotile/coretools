from pymomo.exceptions import *
from pymomo.utilities.typedargs.annotate import param, returns
from itertools import tee, izip
from collections import namedtuple

def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return izip(a, b)

def parse_gpsim_log_statement(statement):
	cycle,value = statement.split(' ')

	cycle = int(cycle)
	value = int(value)

	if value != 0 and value != 1:
		raise InternalError("Invalid i2c log statement", statement=statement)

	return cycle, value

StartCondition = namedtuple("StartEvent", ['cycle'])
RepeatedStartCondition = namedtuple("RepeatedStartEvent", ['cycle'])
StopCondition = namedtuple("StopEvent", ['cycle'])
DataByte = namedtuple("DataByte", ['start_cycle', 'end_cycle', 'value', 'acked'])
AddressByte = namedtuple("AddressByte", ['start_cycle', 'end_cycle', 'address', 'is_write', 'acked'])

class I2CAnalyzer:
	"""
	Given a list of the states the clock and data lines at various sample points,
	decode the i2c sequence and convert it to logical operations: start, write, read
	etc.  
	"""

	ClockRisingEdge 	  = 1
	StartCondition		  = 2
	StopCondition 		  = 3
	UnclassifiedCondition = 4

	def __init__(self, states, ignore_errors=False):
		"""
		Take in a list of tuples of the form (cycle, clock, data) where
		cycle is a monotonically increasing cycle counter (time measured
		in arbitrary units), clock is a 0 for low or 1 for high and data 
		is a 0 for low and 1 for high.
		"""

		self.raw_states = [x for x in states]
		self.processed_states = []

		#Process from raw samples to semantic events on the bus
		for last, curr in pairwise(self.raw_states):
			trans = self._classify_state(last, curr)

			if trans != self.UnclassifiedCondition:
				self.processed_states.append((trans, curr[0], curr[2]))

		#Process semantic events into logical events (Start, Byte, Repeated Start, Stop)
		states = self.processed_states
		self.bus_events = []

		try:
			while len(states) > 0:
				trans, states = self._process_transaction(states, ignore_errors=ignore_errors)

				if len(trans) == 0:
					break

				self.bus_events.extend(trans)
		except InternalError:
			if ignore_errors:
				print "Error processing some states, using states until error occurred."
			else:
				raise

	def _is_byte_transmission(self, states):
		if len(states) != 9:
			return False

		for i in xrange(0, 9):
			if states[i][0] != self.ClockRisingEdge:
				return False

		return True

	def _process_byte(self, states):
		bits = map(lambda x: x[2], states)

		byte = 0
		for i in xrange(0, 8):
			byte <<= 1
			byte |= bits[i] & 0x1

		ack = not bool(bits[8])

		return (states[0][1], states[-1][1], byte, ack)

	def _process_address(self, start, end, value, acked):
		addr = value >> 1
		write = not bool(value & 0x1)

		return AddressByte(start, end, addr, write, acked)

	def _process_transaction(self, states, ignore_errors=False):
		"""
		Process a Start, [Byte...], [Repeated Start...], Stop Series
		"""

		trans = []

		if states[0][0] != I2CAnalyzer.StartCondition:
			raise InternalError("Transaction did not start with StartEvent", initial_state = states[0])

		trans.append(StartCondition(states[0][1]))

		i=1
		while i < len(states):
			#Attempt to parse another byte
			if len(states) - i >= 9:
				potential_byte = states[i:i+9]
				if self._is_byte_transmission(potential_byte):
					start, end, value, acked = self._process_byte(potential_byte)
					if isinstance(trans[-1], StartCondition) or isinstance(trans[-1], RepeatedStartCondition):
						trans.append(self._process_address(start, end, value, acked))
					else:
						trans.append(DataByte(start, end, value, acked))

					i += 9
					continue

			#Check if it's a stop or repeated start
			#These may be preceded by rising clock edges to get the 
			#sda value correct
			if states[i][0] == self.StopCondition:
				trans.append(StopCondition(states[i][1]))
				i += 1
			elif states[i][0] == self.ClockRisingEdge and (i+1) < len(states) and states[i+1][0] == self.StartCondition:
				trans.append(RepeatedStartCondition(states[i+1][1]))
				i += 2
			elif states[i][0] == self.StartCondition:
				trans.append(RepeatedStartCondition(states[i][1]))
				i += 1
			elif states[i][0] == self.ClockRisingEdge and (i+1) < len(states) and states[i+1][0] == self.StopCondition:
				trans.append(StopCondition(states[i+1][1]))
				i += 2
				break
			elif states[i][0] == self.StopCondition:
				trans.append(StopCondition(states[i][1]))
				i += i
				break
			else:
				if ignore_errors:
					break

				raise InternalError("Invalid I2C State", state=states[i])

		if not ignore_errors and not isinstance(trans[-1], StopCondition):
			raise InternalError("I2C Transaction did not end with a STOP", last_state=trans[-1])

		return trans, states[i:]

	def _classify_state(self, last, state):
		"""
		Classify the transition that occured between the last state and this one
		"""

		scl_l = last[1]
		scl_c = state[1]
		sda_l = last[2]
		sda_c = state[2]

		#Transitions while scl are high indicate start and stop
		if scl_l == 1 and scl_c == 1:
			if sda_l == 1 and sda_c == 0:
				return I2CAnalyzer.StartCondition
			elif sda_l == 0 and sda_c == 1:
				return I2CAnalyzer.StopCondition
			else:
				return I2CAnalyzer.UnclassifiedCondition

		if scl_l == 0 and scl_c == 1:
			return I2CAnalyzer.ClockRisingEdge

		return I2CAnalyzer.UnclassifiedCondition 

	def _format_start(self, ev, short):
		if short:
			return "S"

		return "%d) Start" % ev.cycle

	def _format_repeated_start(self, ev, short):
		if short:
			return "RS"

		return "%d) Repeated Start" % ev.cycle

	def _format_stop(self, ev, short):
		if short:
			return "P"

		return "%d) Stop" % ev.cycle
	
	def _format_data(self, ev, short):
		a = 'NACK'
		if ev.acked:
			a = 'ACK'

		if short:
			return "0x%x/%s" % (ev.value, a[0])

		return "%d) 0x%x %s" % (ev.start_cycle, ev.value, a)

	def _format_address(self, ev, short):
		a = 'NACK'
		if ev.acked:
			a = 'ACK'

		d = 'READ from'
		if ev.is_write:
			d = 'WRITE to'

		if short:
			return "0x%x/%s%s" % (ev.address, d[0], a[0])

		return "%d) %s 0x%x %s" % (ev.start_cycle, d, ev.address, a)

	def _format_event(self, ev, **kwargs):
		if isinstance(ev, StartCondition):
			return self._format_start(ev, **kwargs)
		elif isinstance(ev, StopCondition):
			return self._format_stop(ev, **kwargs)
		elif isinstance(ev, DataByte):
			return self._format_data(ev, **kwargs)
		elif isinstance(ev, AddressByte):
			return self._format_address(ev, **kwargs)
		elif isinstance(ev, RepeatedStartCondition):
			return self._format_repeated_start(ev, **kwargs)
		
		raise InternalError("Unknown event type in i2c log, cannot format", event=ev)

	def format(self, short=False):
		"""
		Format this i2c log for printing
		"""

		log = []

		for ev in self.bus_events:
			log.append(self._format_event(ev, short=short))

		if short:
			return ", ".join(log)
		
		return "\n".join(log)

	@classmethod
	@param("clock_path", "path", "readable", desc="Path to GPSIM log of i2c clock signal")
	@param("data_path", "path", "readable", desc="Path to GPSIM log of i2c data signal")
	@param("ignore_errors", "bool", desc="If the stream is not valid, parse only the valid part")
	def FromGPSIMLogs(cls, clock_path, data_path, ignore_errors=False):
		with open(clock_path, "r") as f:
			clk = f.readlines()
			clk = [x.rstrip().lstrip() for x in clk if x.rstrip().lstrip() != ""]

		with open(data_path, "r") as f:
			dat = f.readlines()
			dat = [x.rstrip().lstrip() for x in dat if x.rstrip().lstrip() != ""]

		if len(clk) % 2 != 0 or len(dat) % 2 != 0:
			raise InternalError("Invalid gpsim log file lengths were not even", data_length=len(dat), clock_length=len(clk))

		clk = clk[::2]
		dat = dat[::2]

		curr_clock = 1
		curr_data = 1
		curr_cycle = -100

		#Read all of the samples
		clock_samples = [("clock", parse_gpsim_log_statement(x)) for x in clk]
		data_samples = [("data", parse_gpsim_log_statement(x)) for x in dat]
		samples = clock_samples + data_samples

		processed = [(curr_cycle, 1, 1)]

		for s in sorted(samples, key=lambda x: x[1][0]):
			val = s[1][1]
			cycle = s[1][0]

			if cycle < curr_cycle:
				raise InternalError("Non-monotonic cycle counter", sample=s, current_cycle=curr_cycle)

			if s[0] == 'clock' and val != curr_clock:
				#process a clock edge
				curr_cycle = cycle
				curr_clock = val
				sample = (cycle, curr_clock, curr_data)
				processed.append(sample)
			elif s[0] == 'data' and val != curr_data:
				curr_cycle = cycle
				curr_data = val
				sample = (cycle, curr_clock, curr_data)
				processed.append(sample)

		return I2CAnalyzer(processed, ignore_errors=ignore_errors)