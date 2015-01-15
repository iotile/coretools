#i2c.py

class I2CMasterSequence:
	start_delay = 100
	half_baud = 5

	def __init__(self, start):
		self.start = start
		self.scl = []
		self.sda = []
		self.comments = []
		self.cycle_count = start

	def _scl_state(self):
		if len(self.scl) == 0:
			return 1

		return self.scl[-1][1]

	def _sda_state(self):
		if len(self.sda) == 0:
			return 1

		return self.sda[-1][1]

	def _verify_idle(self):
		if self._scl_state() == 1 and self._sda_state() == 1:
			return True

		return False

	def sda_trans(self, value, delay):
		self.sda.append((self.cycle_count+delay, value))
		self.cycle_count += delay

	def scl_trans(self, value, delay):
		self.scl.append((self.cycle_count+delay, value))
		self.cycle_count += delay

	def _print_bus(self):
		return "SDA:%d , SCL: %d" % (self.sda[-1][1], self.scl[-1][1])

	def send_start(self):
		if self._sda_state() == 0:
			self.sda_trans(1, 5)

		if self._scl_state() == 0:
			self.scl_trans(1, 5)

		if not self._verify_idle():
			raise ValueError("Tried to send a start with the bus not idle: %s" % self._print_bus())

		self.sda_trans(0, 20)
		self.scl_trans(0, 20)

	def send_bit(self, val):
		if self._scl_state() != 0:
			raise ValueError("Starting a bit when SCL is high.")

		self.sda_trans(val, self.half_baud)
		self.scl_trans(1, self.half_baud*2)
		self.scl_trans(0, self.half_baud)

	def delay(self, val):
		self.cycle_count += val

	def send_byte(self, val):
		val = val << 1
		
		for i in xrange(0,9):
			bitnum = 8-i
			bit = (val & (1 << bitnum)) >> bitnum
			self.send_bit(bit)

	def report(self):
		sda = map(lambda x: ('SDA', x[0], x[1]), self.sda)
		scl = map(lambda x: ('SCL', x[0], x[1]), self.scl)

		comb= sda + scl

		rep = sorted(comb, key=lambda x: x[1])

		for name,delay,val in rep:
			print "%d: %s=%d" % (delay, name, val)

	def write(self, addr, bytes):
		if not self._verify_idle():
			raise ValueError("Do not support repeated start yet")

		self.send_start()
		abyte = addr<<1

		self.send_byte(abyte)

		self.delay(1000)

		for byte in bytes:
			self.send_byte(byte)
			self.delay(1000)

	def read(self, addr):
		"""
		Send a (repeated) start along with an address with read indication
		"""
		self.send_start()
		abyte = addr<<1 | 1

		self.send_byte(abyte)

	def _gpsim_header(self):
		h = "stimulus asynchronous_stimulus\n"
		h += "initial_state 1\n"
		h += "start_cycle %d\n" % self.start
		h += "{ "

		return h

	def _gpsim_trailer(self, name):
		t = "name %s\n" % name
		t += "end\n"

		return t

	def to_gpsim(self, scl_name, sda_name):
		"""
		return two name stimuli definitions compatible with gpsim
		"""

		scl = self._gpsim_header()
		sda = self._gpsim_header()

		for delay, val in self.scl:
			scl += "%d, %d,\n" % (delay, val)

		scl = scl[:-2]
		scl += " }\n"

		for delay, val in self.sda:
			sda += "%d, %d,\n" % (delay, val)

		sda = sda[:-2]
		sda += " }\n"

		scl += self._gpsim_trailer(scl_name)
		sda += self._gpsim_trailer(sda_name)

		return {'SDA':sda, 'SCL':scl}

	@classmethod
	def checksum(cls, bytes):
		s = 0

		for byte in bytes:
			s += byte

		return (~s) + 1

seq = I2CMasterSequence(1000)

cmd = [10, 0, 0]
cmd.append(seq.checksum(cmd))

seq.write(10, cmd)
seq.read(10)

vals = seq.to_gpsim('scl_seq', 'sda_seq')

print vals['SCL']
print vals['SDA']