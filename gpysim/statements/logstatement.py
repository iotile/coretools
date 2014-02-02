
class LogStatement:
	def pull_info(self, log):
		self.address = log.current_address

	def keep(self):
		"""
		Override in subclasses if this logging statement doesn't stand on its own but 
		just sets state for future logging statements.  It will be processed and then
		deleted from the Log object list of logging statements
		"""
		return True

	def error(self):
		"""
		Override for logging statements that indicate errors, rather than ones that are just informational
		"""
		return False

	def format_line(self, symtab, use_colors):
		HEADER = '\033[95m'
		OKBLUE = '\033[94m'
		OKGREEN = '\033[92m'
		WARNING = '\033[93m'
		FAIL = '\033[91m'
		ENDC = '\033[0m'

		func = None

		color = OKBLUE
		if self.error():
			color = FAIL

		if use_colors is not True:
			HEADER = ''
			color = ''
			ENDC = ''

		if symtab is not None:
			func = symtab.map_address(self.address)

		header = 'Address 0x%X: ' % self.address
		if func is not None:
			header = HEADER + '%s+%d: ' % (func[0], func[1]) + ENDC

		return header + color + self.format() + ENDC