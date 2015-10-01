#log.py
#Parse the log file from a gpsim test run and convert it to a series of events

import re
import statements
from statements.unknown import UnknownStatement
from pymomo.hex8 import symbols

class LogFile:	
	def __init__(self, filename, symtab=None):
		with open(filename, "r") as f:
			lines = f.readlines()

		self.entries = []
		self.symtab = symtab

		#initialize program counter
		self.current_address = 0

		#Only keep entries where we write to the logging registers	
		lines = filter(lambda x: not x.startswith('  Read:'), lines)
		lines = filter(lambda x: not x.startswith('  BREAK:'), lines)
		lines = filter(lambda x: not x.rstrip().endswith('sleep'), lines)
		lines = filter(lambda x: not x.startswith('  Wrote:') or 'to ccpr1l(0x0291)' in x or 'to ccpr1h(0x0292)' in x, lines)

		if len(lines) % 2 != 0:
			print lines
			raise ValueError("File length is invalid, filtered entries should be a multiple of 2, len=%d." % len(lines))

		if len(lines) == 0:
			self.entries = []
			return

		entries = zip(lines[0::2], lines[1::2])
		entries = map(lambda x: (x[0]+x[1]).rstrip(), entries)
		entries = map(lambda x: re.split('\W+', x), entries)
		info = map(extract_info, entries)
		info = info[:-1] #chomp last entry which is always a duplicate of test ended

		#find control entries
		controls = filter(lambda x: x[1]['dest'] == 'ccpr1l', enumerate(info))
		controls = map(lambda x: x[0], controls)
		lengths = [x-controls[i] for i,x in enumerate(controls[1:])]

		lengths.append(1) #final control statement has no data entries

		if len(lengths) != len(controls):
			raise ValueError("Logic error in log file handling, control statements were not matched with data statements")

		#at this point we have the indices corresponding to all control statements
		#and their lengths build the statements
		statements = [{'control': info[c], 'data':info[c+1:c+lengths[i]]} for i,c in enumerate(controls)]
		entries = map(lambda x:self._process_statement(x), statements)
		
		self.entries = filter(lambda x:x.keep() == True, entries)

	def _process_statement(self, statement):
		if statement['control']['value'] in statements.statements:
			return statements.statements[statement['control']['value']](statement, self)

		return UnknownStatement(statement, self)

	def pretty_print(self, color=True):
	    for entry in self.entries:
	    	print entry.format_line(self.symtab, use_colors=color)

	def save(self, path):
		with open(path, "w") as f:
			for entry in self.entries:
				f.write(entry.format_line(self.symtab, use_colors=False) + '\n')

	def test_passed(self, testcase):
		for entry in self.entries:
			if entry.error():
				return False

		if testcase.ignore_checkpoints:
			return True

		#Make sure that all checkpoints were passed and logged the correct values
		pts = testcase.checkpoints

		passed_pts = [x for x in self.entries if isinstance(x, statements.logcheckpoint.LogCheckpoint)]

		if len(pts) != len(passed_pts):
			return False

		#Make sure the symbol and value match for each passed checkpoint
		for expected, passed in zip(pts, passed_pts):
			if self.symtab.map_address(passed.address) is None:
				return False

			passed_sym = self.symtab.map_address(passed.address)[0]

			if passed_sym != expected[0]:
				return False
			if expected[1] != passed.data:
				return False

		return True

def extract_info(entry):
	info = {}

	if len(entry) != 13:
		raise ValueError("Invalid entry had illegal length %d" % len(entry))

	info['cycle'] = int(entry[0],0)
	info['proc'] = entry[1]
	info['value'] = int(entry[7],0)
	info['dest'] = entry[9]

	return info