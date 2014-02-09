#config12.py

from pymomo.utilities import build

class MIB12Processor:
	"""
	Collection of settings pertaining to the location of various important
	ROM and RAM regions in the MIB12 framework.
	"""

	def __init__(self, name, settings):
		self.settings = settings
		self.name = name

		self._calculate()

	def _calculate(self):
		self.exec_rom = self.settings['executive_rom']
		self.app_rom = [self.exec_rom[1] +1, self.settings['total_rom']-1]

		self.api_range = [self.app_rom[0] - 16, self.app_rom[0] - 1]
		self.mib_range = [2048 - 16, 2047] #mib map is 16 bytes long

		self.row_size = self.settings['flash_row_words']
		self.total_prog_mem = self.settings['total_rom']
		self.first_app_page = self.app_rom[0] / self.row_size

	@classmethod
	def FromChip(cls, chip):
		"""
		Create a processor instance from a valid chip name defined in build_settings.json
		"""

		aliases, info = build.load_chip_info(chip)
		return MIB12Processor(chip, info)