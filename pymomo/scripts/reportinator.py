#!/usr/bin/env python

import sys, os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pymomo.commander.hwmanager import HardwareManager
from pymomo.commander.exceptions import *
from pymomo.commander.proxy import *

import cmdln
import struct
import base64
import datetime

from random import randint

def chunk(l, n):
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

class Reportinator(cmdln.Cmdln):
	name = 'reportinator'

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_reset(self, subcmd, opts):
		"""${cmd_name}: Reset report configuration

		${cmd_usage}
		${cmd_option_list}
		"""
		con = self._get_controller( opts )
		con.reset_reporting_config()

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_start(self, subcmd, opts):
		"""${cmd_name}: Start reporting

		${cmd_usage}
		${cmd_option_list}
		"""
		con = self._get_controller( opts )
		con.start_reporting()

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_stop(self, subcmd, opts):
		"""${cmd_name}: Stop reporting

		${cmd_usage}
		${cmd_option_list}
		"""
		con = self._get_controller( opts )
		con.stop_reporting()

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_state(self, subcmd, opts):
		"""${cmd_name}: Get the current state of the autonomous reporting flag.

		${cmd_usage}
		${cmd_option_list}
		"""
		con = self._get_controller( opts )
		if con.get_reporting():
			print "Enabled"
		else:
			print "Disabled"


	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_send(self, subcmd, opts):
		"""${cmd_name}: Send a single report

		${cmd_usage}
		${cmd_option_list}
		"""
		con = self._get_controller( opts )
		con.send_report();

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_routes(self, subcmd, opts, primary=None, secondary=None):
		"""${cmd_name}: Get or set the destination address for reporting.

		${cmd_usage}
		${cmd_option_list}
		"""
		con = self._get_controller( opts )
		if primary != None:
			con.set_report_route(0, primary)
			if secondary == "" or secondary != None:
				con.set_report_route(1, secondary)

		primary = con.get_report_route(0);
		secondary = con.get_report_route(1);
		print "primary:   %s" % (primary)
		print "secondary: %s" % (secondary)

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_apn(self, subcmd, opts, apn=None):
		"""${cmd_name}: Get or set the GPRS APN.

		${cmd_usage}
		${cmd_option_list}
		"""

		con = self._get_controller( opts )
		if apn != None:
			con.set_gprs_apn(apn)
		print con.get_gprs_apn()

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_interval(self, subcmd, opts, interval=None):
		"""${cmd_name}: Get or set the reporting interval.

		${cmd_usage}
		${cmd_option_list}
		"""
		con = self._get_controller( opts )
		if ( interval != None ):
			con.rpc( 60, 0x03, int(interval))
		interval = con.rpc( 60, 0x04, result_type=(1,False) );
		print "%d" % interval['ints'][0]

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_flags(self, subcmd, opts, flags=None):
		"""${cmd_name}: Get or set the report flags.

		${cmd_usage}
		${cmd_option_list}
		"""
		con = self._get_controller( opts )
		if ( flags != None ):
			con.rpc( 60, 0x07, int(flags))
		flags = con.rpc( 60, 0x08, result_type=(1,False) );
		print "%d" % flags['ints'][0]

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_aggregates(self, subcmd, opts, bulk=None, interval=None):
		"""${cmd_name}: Get or set the report aggregates.

		${cmd_usage}
		${cmd_option_list}
		"""
		con = self._get_controller( opts )
		if ( bulk != None and interval != None ):
			con.rpc( 60, 0x09, int(bulk), int(interval))
		aggregates = con.rpc( 60, 0x0A, result_type=(2,False) );
		print "bulk:     %d" % aggregates['ints'][0]
		print "interval: %d" % aggregates['ints'][1]

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_sequence(self, subcmd, opts):
		"""${cmd_name}: Get the current report sequence.

		${cmd_usage}
		${cmd_option_list}
		"""
		con = self._get_controller( opts )
		sequence = con.rpc( 60, 0x0B, result_type=(1,False) );
		print "%d" % sequence['ints'][0]

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_log(self,subcmd, opts, cmd, limit=None):
		"""${cmd_name}: Manage the log of reports, succeeded and failed.

		Subcommands:
		- count - return the number of reports in the log
		- read <limit> - read <limit> (or all if <limit> is omitted) reports from the log
		- clear - clear the log (USE AT YOUR OWN RISK)

		${cmd_usage}
		${cmd_option_list}
		"""

		con = self._get_controller(opts)
		if cmd == 'read':
			index = 0
			if limit != None:
				count = con.rpc( 60, 0x10, result_type=(1,False) )['ints'][0]
				limit = int(limit)
				if limit > count:
					limit = count
				index = count - limit
			while True:
				offset = 0
				report = ''
				while offset < 118:
					try:
						res = con.rpc( 60, 0x0F, index, offset, result_type=(0,True) )
					except RPCException as e:
						if e.type != 7:
							raise e
						break
					offset += len(res['buffer'])
					report += res['buffer']
				if len(report) == 0:
					break
				print base64.b64encode(report)
				index += 1
		elif cmd == 'count':
			res = con.rpc( 60, 0x10, result_type=(1,False) )
			print res['ints'][0]
		elif cmd == 'clear':
			res = con.rpc( 60, 0x11 )
			print "All items cleared from the report log."
		else:
			print "Invalid subcommand passed to log command."

	def do_parse(self, subcmd, opts, report):
		"""${cmd_name}: Parse a report in BASE64 format

		${cmd_usage}
		${cmd_option_list}
		"""

		agg_names = ['count','sum','mean','<none>','<none>','min','max']
		interval_types = ['second', 'minute', 'hour', 'day']
		report = base64.b64decode(report)

		version = ord(report[0])
		if version == 2:
			sensor, sequence, flags, battery_voltage, diag1, diag2, bulk_aggs, int_aggs, interval_def, interval_count = struct.unpack( "xBHHHHHBBBB", report[:16] )

			interval_type = interval_def & 0xF
			interval_step = interval_def >> 4
			if interval_type > len(interval_types):
				interval_type = "<unknown:%d>" % interval_type
			else:
				interval_type = interval_types[interval_type]

			bulk_agg_names = []
			for i in range(0,7):
				if ( bulk_aggs & (0x1 << i) ):
					bulk_agg_names.append(agg_names[i])

			int_agg_names = []
			for i in range(0,7):
				if ( int_aggs & (0x1 << i) ):
					int_agg_names.append(agg_names[i])

			print "version: 2"
			print "sensor: %d" % sensor
			print "sequence: %d" % sequence
			print "flags: %d" % flags
			print "battery charge: %.2fV" % ( float(battery_voltage) / 1024 * 2.78 * 2)
			print "diag: %d, %d" % (diag1, diag2)
			print "Interval type: %s" % interval_type
			print "         step: %d" % interval_step
			print "        count: %d" % interval_count

			if bulk_aggs != 0:
				print "Global aggregates:"
				values = struct.unpack( "H" * len(bulk_agg_names), report[16:16+len(bulk_agg_names)*2] )
				for i in range( len(values) ):
					print "\t%s = %d" % (bulk_agg_names[i], values[i])

			if int_aggs != 0:
				print "Interval Aggregates:"
				interval_aggregate_slice = report[16+len(bulk_agg_names)*2:16+len(bulk_agg_names)*2+interval_count*len(int_agg_names)*2]
				values = struct.unpack( "H" * len(int_agg_names) * interval_count, interval_aggregate_slice )
				row_format ="{:>8}" * (len(int_agg_names) + 1)
				print row_format.format("", *int_agg_names)
				for row in chunk(values, len(int_agg_names)):
					print row_format.format("", *row)
		elif version == 3:
			sequence, uuid, flags, timestamp, battery_voltage, bulk_aggs, int_aggs, interval_def, interval_count = struct.unpack( "<xBLHLHBBBB", report[:18] )

			interval_type = interval_def & 0xF
			interval_step = interval_def >> 4
			if interval_type > len(interval_types):
				interval_type = "<unknown:%d>" % interval_type
			else:
				interval_type = interval_types[interval_type]

			bulk_agg_names = []
			for i in range(0,7):
				if ( bulk_aggs & (0x1 << i) ):
					bulk_agg_names.append(agg_names[i])

			int_agg_names = []
			for i in range(0,7):
				if ( int_aggs & (0x1 << i) ):
					int_agg_names.append(agg_names[i])

			print "version: 3"
			print "transmit sequence: %d" % sequence
			uuid = struct.pack('<L', uuid)
			print "UUID: %s" % base64.b64encode(uuid).rstrip('=')
			print "flags: %d" % flags
			print "timestamp: %s" % datetime.datetime.utcfromtimestamp(timestamp + 946684800)
			print "battery charge: %.2fV" % ( float(battery_voltage) / 1024 * 2.78 * 2)
			print "Interval type: %s" % interval_type
			print "         step: %d" % interval_step
			print "        count: %d" % interval_count

			if bulk_aggs != 0:
				print "Global aggregates:"
				values = struct.unpack( "H" * len(bulk_agg_names), report[18:18+len(bulk_agg_names)*2] )
				for i in range( len(values) ):
					print "\t%s = %d" % (bulk_agg_names[i], values[i])

			if int_aggs != 0:
				print "Interval Aggregates:"
				interval_aggregate_slice = report[18+len(bulk_agg_names)*2:18+len(bulk_agg_names)*2+interval_count*len(int_agg_names)*2]
				values = struct.unpack( "H" * len(int_agg_names) * interval_count, interval_aggregate_slice )
				row_format ="{:>8}" * (len(int_agg_names) + 1)
				print row_format.format("", *int_agg_names)
				for row in chunk(values, len(int_agg_names)):
					print row_format.format("", *row)
		else:
			print "Unrecognized report version %d" % ord(report[0])
			return

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_test(self, subcmd, opts):
		con = self._get_controller( opts )
		
		second = 0
		minute = 0
		hour = 0
		day = 1

		con.set_time( 14, 1, day, hour, minute, second )
		while ( True ):
			con.sensor_log( 0, 0, randint(1,1000) )
			
			second += 60
			if ( second == 60 ):
				second = 0
				minute += 1
				if ( minute == 60 ):
					minute = 0
					hour += 1
					if hour == 24:
						hour = 0
						day += 1
						break
			print day, hour, minute, second
			con.set_time( 14, 1, day, hour, minute, second )

	def _get_controller(self,opts):
		con = HardwareManager(opts.port).controller()
		return con

def main():
	reportinator = Reportinator()
	return reportinator.main()