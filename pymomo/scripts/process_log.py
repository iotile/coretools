#pv_log.py
#Process the log file created by the pv_module into a csv file

import sys
import csv
import cmdln
import struct
import os.path

class LogFile:
	intervals = {'1s': 0, '2s': 1, '4s': 2,'8s': 3,'16s': 4,'32s': 5,'64s': 6,'128s': 7,'256s': 8}
	int_times = [1, 2 ,4 , 8, 16, 32, 64, 128, 256]
	inv_map = ['1 second', '2 seconds', '4 seconds','8 seconds','16 seconds','32 seconds','64 seconds','128 seconds','256 seconds']

	default_int = 6

	def __init__(self, path):
		self.size = os.path.getsize(path)
		self.file = open(path, "r+b")
		self._read_info()
		self._calculate()

	def _read_info(self):
		self.file.seek(0)
		fmt = "<IIB"

		data = self.file.read(9)

		(magic, valid_sectors, int_num) = struct.unpack(fmt, data)


		if magic == 0x78563412:
			self.valid_file = True
			self.valid_sectors = valid_sectors-1

			if int_num < len(self.inv_map):
				self.interval = self.inv_map[int_num]
				self.intnum = int_num
			else:
				self.interval = "INVALID (value=%d)" % int_num
				self.intnum = self.default_int

		else:
			self.valid_file = False
			self.valid_sectors = -1
			self.interval = "INVALID"
			self.intnum = self.default_int

	def _calculate(self):
		self.num_entries = self.valid_sectors * 512 / 16
		self.remaining = (self.size - 512) / 16 - self.num_entries
		self.time_remaining = self.remaining * self.int_times[self.intnum] / 60 / 60 / 24

	def process(self, v1, v2, v3, i1):
		v1_o = v1/1024. * 20*2.8/2.78
		v2_o = v2/1024. * 20*2.8/2.78
		v3_o = v3/1024. * 25*2.8/2.78
		i1_o = i1/1024. * 2.78 / 0.001 / 100

		return {"v1": v1_o, "v2": v2_o, "v3": v3_o, "i1": i1_o}

	def enum_entries(self, skip, num):
		entry_fmt = "<IIHHHH"
		
		if num < 0:
			num = self.num_entries

		for i in xrange(skip, min(self.num_entries, skip+num)):
			self.file.seek(512 + i*16)
			data = self.file.read(16)
			(mag1, mag2, v1, v2, v3, i1) = struct.unpack(entry_fmt, data)

			if mag1 != 0xDDCCBBAA or mag2 != 0x9955FFEE:
				continue

			yield ((v1, v2, v3, i1), self.process(v1, v2, v3, i1))

	def map_interval(self, interval):
		if interval in self.intervals:
			return self.intervals[interval]

		return self.default_int

	def close(self):
		self.file.close()

	def write_toc(self, valid, interval):
		self.file.seek(0)
		
		fmt = "<IIB"

		if interval is None:
			interval = self.intnum
		elif interval not in self.intervals:
			print "WARNING: Invalid interval specified, using default value"

		int_num = self.map_interval(interval)

		#A valid value < 1 means to keep the current number of valid sectors
		if valid < 1:
			valid = self.valid_sectors+1

		header = struct.pack(fmt, 0x78563412, max(valid, 1), int_num)
		self.file.write(header)
		self.file.flush()

class PVCommands(cmdln.Cmdln):
	name = 'pv_log'

	def do_info(self, subcmd, opts, log_file):
		"""${cmd_name}: Print info about the log file specified

		Detailed information is given about the number of log entries,
		the log file size and other interesting information.
		${cmd_usage}
		${cmd_option_list}
		LOG_FILE should be a path to a log file (log.bin) produced by the
		MoMo solar logging module.
		"""

		try:
			log = LogFile(log_file)
		except IOError:
			print "Error: could not open log file: %s" % log_file
			return 1

		print "Log File Information"
		print "File Valid: %s" % log.valid_file
		print "Number of Sectors Used: %d" % log.valid_sectors
		print "Number of Datapoints Logged: %d" % log.num_entries 
		print "Logging Interval: %s (numerical value %d) " % (log.interval, log.intnum)
		print "Space Remaining: %d entries" % log.remaining
		print "Time Remaining: %d days" % log.time_remaining
		return 0

	@cmdln.option('-s', '--skip', action='store', type=int, default=0, help='skip the first SKIP entries')
	@cmdln.option('-n', '--num', action='store', type=int, default=-1, help='print only NUM entries')
	def do_print(self, subcmd, opts, log_file):
		"""${cmd_name}: Print all or a subset of the log entries to stdout

		${cmd_usage}
		${cmd_option_list}
		LOG_FILE should be a path to a log file (log.bin) produced by the
		MoMo solar logging module.
		"""

		try:
			log = LogFile(log_file)
		except IOError:
			print "Error: could not open log file: %s" % log_file
			return 1

		for raw, proc in log.enum_entries(opts.skip, opts.num):
			print "V1: %.2fV || V2: %.2fV || V3: %.2fV || Current: %.2fA" % (proc['v1'], proc['v2'], proc['v3'], proc['i1'])

		return 0

	@cmdln.option('-o', '--out', action='store', default='log.csv', help='output CSV file to be generated')
	@cmdln.option('-s', '--skip', action='store', type=int, default=0, help='skip the first SKIP entries')
	@cmdln.option('-n', '--num', action='store', type=int, default=-1, help='print only NUM entries')
	def do_convert(self, subcmd, opts, log_file):
		"""${cmd_name}: Convert a binary log file (log.bin) to a CSV spreadsheet

		${cmd_usage}
		${cmd_option_list}
		LOG_FILE should be a path to a log file (log.bin) produced by the
		MoMo solar logging module.
		"""

		try:
			log = LogFile(log_file)
		except IOError:
			print "Error: could not open log file: %s" % log_file
			return 1

		try:
			out = open(opts.out, "w")
			writer = csv.writer(out, lineterminator='\n')
		except IOError:
			log.close()
			print "Error: could not create output file: %s" % opts.out
			return 1

		headers = ['Voltage 1 (V)', 'Voltage 2 (V)', 'Voltage 3 (V)', 'Current (A)', 'Raw V1', 'Raw V2', 'Raw V3', 'Raw Current']
		writer.writerow(['WellDone PV Logging Module v1'])
		writer.writerow(['Logging Interval: %s' % log.interval])
		writer.writerow(headers)
		for raw, proc in log.enum_entries(opts.skip, opts.num):
			row = [proc['v1'], proc['v2'], proc['v3'], proc['i1'], raw[0], raw[1], raw[2], raw[3]]
			writer.writerow(row)

		out.close()

		return 0

	@cmdln.option('-s', '--size', action='store', type=int, default=1024*1024*128, help='file size (default is 128MB)')
	@cmdln.option('-i', '--interval', type='choice', choices=['1s', '2s', '4s','8s','16s','32s','64s','128s','256s'], default='64s', help='Logging interval (default: 64s)')
	def do_create(self, subcmd, opts, directory):
		"""${cmd_name}: Create a new log file in the specified directory

		${cmd_usage}
		${cmd_option_list}
		DIRECTORY should be a path to the root directory of the SD card that 
		will be used for logging.  The log file must be completely preallocated,
		meaning that the size you specify in this command will limit how large of
		a log the data logger can produce.  The logger will log data at the interval
		specified with the -i option.  

		Possible logging intervals are 1s, 4s, 8s, 16s, 32s, 64s (default), 128s and 256s.
		"""

		block = 4096
		numblocks = opts.size / block
		remainder = opts.size % block

		log_file = os.path.join(directory, 'log.bin')

		blockbuff = "\0" * block

		with open(log_file, "w") as f:
			for i in xrange(0, numblocks):
				f.write(blockbuff)

			remblock = "\0" * remainder
			f.write(remblock)

		try:
			log = LogFile(log_file)
		except IOError:
			print "Error: could not open log file: %s" % log_file
			return 1

		log.write_toc(1, opts.interval)
		log.close()

		return 0

	@cmdln.option('-t', '--truncate', action='store_true', help='erase all logged data')
	@cmdln.option('-i', '--interval', type='choice', choices=['1s','2s','4s','8s','16s','32s','64s','128s','256s'], default=None, help='Logging interval (default: 64s)')
	def do_adjust(self, subcmd, opts, log_file):
		"""${cmd_name}: Create a new log file in the specified directory

		${cmd_usage}
		${cmd_option_list}
		Adjust the logging settings specified by this log.bin file.  You can update
		the logging interval and/or erase all of the logged data in the file
		LOG_FILE should be a path to a log file (log.bin) produced by the
		MoMo solar logging module.

		Possible logging intervals are 1s, 4s, 8s, 16s, 32s, 64s (default), 128s and 256s.
		"""

		valid = -1

		if opts.truncate:
			valid = 1

		try:
			log = LogFile(log_file)
		except IOError:
			print "Error: could not open log file: %s" % log_file
			return 1

		log.write_toc(valid, opts.interval)
		log.close()

		return 0

if __name__ == "__main__":
	pv = PVCommands()
	sys.exit(pv.main())