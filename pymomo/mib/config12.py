#config12.py

from pymomo.utilities import build
from pymomo.exceptions import *
from interval import Interval, IntervalSet

class MIB12Processor:
	"""
	Collection of settings pertaining to the location of various important
	ROM and RAM regions in the MIB12 framework.
	"""

	def __init__(self, name, settings):
		self.settings = settings
		self.name = name

		self._calculate_rom()
		self._calculate_ram()

	def _calculate_rom(self):
		self.exec_rom = self.settings['executive_rom']
		self.app_rom = [self.exec_rom[1] + 1, self.settings['total_rom']-1]

		self.api_range = [self.app_rom[0] - 16, self.app_rom[0] - 1]
		self.mib_range = [2048 - 16, 2047] #mib map is 16 bytes long

		self.row_size = self.settings['flash_row_words']
		self.total_prog_mem = self.settings['total_rom']
		self.first_app_page = self.app_rom[0] / self.row_size

	def _build_ram(self, total):
		"""
		Build the set of intervals that correspond to the GPR in 
		a banked PIC12 processor with total RAM = total.
		"""

		ints = []

		if total < 96:
			raise ArgumentError("No supported PIC enhanced midrange processor can have less than 96 bytes of RAM (one full bank)", total_ram=total)

		banked = total - 16

		for bank in xrange(0,32):
			start = 80*bank
			if start < banked:
				end = min(80, banked - start)
				start_addr = 128*bank + 0x20	#the first 32 bytes of each bank are special purpose registers
				ints.append(Interval(start_addr, start_addr + end - 1)) #bounds are inclusive so subtract 1

			start_common = 128*bank + 0x70		#Common ram starts after 80 bytes of banked ram (0x20 + 0x50 = 0x70) 
			ints.append(Interval(start_common, start_common + 16 - 1))

		return IntervalSet(ints)

	def _calculate_ram(self):
		"""
		Calculate the proper exclusion ranges for executive and
		applicaiton RAM and store them.
		"""

		exec_ram = IntervalSet(map(lambda x: Interval(x[0], x[1]), self.settings['executive_ram']))
		total_ram = self._build_ram(self.settings['total_ram'])

		self.exec_ram = map(lambda x: (x.lower_bound, x.upper_bound), exec_ram.intervals)
		self.app_ram = map(lambda x: (x.lower_bound, x.upper_bound), (total_ram - exec_ram).intervals)
		self.total_ram_size = self.settings['total_ram']

	@classmethod
	def FromChip(cls, chip):
		"""
		Create a processor instance from a valid chip name defined in build_settings.json
		"""

		fam = build.ChipFamily('mib12')
		info = fam.find(chip)

		return MIB12Processor(chip, info.settings)