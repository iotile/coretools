#!/usr/bin/env python

import sys, os
from time import sleep

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pymomo.commander.meta import *
from pymomo.commander.exceptions import *
from pymomo.commander.proxy import *

import time
import cmdln

class SensorTool(cmdln.Cmdln):
	name = 'multisensor'

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-a', '--address', help='The MIB address of the multisensor module' )
	@cmdln.option('-n', '--average', type=int, default=1, help='Average for N samples' )
	@cmdln.option('-c', '--continuous', action='store_true', default=False, help='Continually sample and report' )
	def do_read(self, subcmd, opts):
		"""${cmd_name}: Read the voltage from the multisensor module

		${cmd_usage}
		${cmd_option_list}
		"""

		sens = self._create_proxy(opts)

		while True:
			v = self._average(sens, opts.average)
			print "Voltage: %d" % v

			if not opts.continuous:
				break

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-a', '--address', help='The MIB address of the multisensor module' )
	def do_set(self, subcmd, opts, name, value):
		"""${cmd_name}: Set the parameter 'name' to the value 'value'

		Valid parameter names are: offset, gain1, gain2, select, invert and delay
		Valid values are: offset: [0, 255], gain1: [0,127], gain2: [0,7], 
		select: [current|differential], invert: [yes|no], delay: [1, 255]

		${cmd_usage}
		${cmd_option_list}
		"""

		sens = self._create_proxy(opts)
		sens.set_parameter(name, value)

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-a', '--address', help='The MIB address of the multisensor module' )
	@cmdln.option('-c', '--continuous', action='store', type=int, default=5, help='Continually sample and report' )
	def do_pulse(self, subcmd, opts):
		"""${cmd_name}: Sample the pulse counters and return the average pulse rate

		Optionally sample continously with a delay between each report.  The delay should between
		at least 4 seconds to allow for one complete sampling cycle per report.
		${cmd_usage}
		${cmd_option_list}
		"""

		sens = self._create_proxy(opts)

		while True:
			val = sens.pulse_rate()
			sens.clear_counters()
			print "Pulse Count: %.2f pulses per second" % val
			
			if not opts.continuous:
				break

			time.sleep(opts.continuous)

	def _create_proxy(self,opts):
		try:
			con = get_controller(opts.port)
			address = 11
			if opts.address != None:
				address = opts.address
			gsm = MultiSensorModule(con.stream, address)
		except NoSerialConnectionException as e:
			print "Available serial ports:"
			if not e.available_ports():
				print "<none>"
			else:
				for port, desc, hwid in e.available_ports():
					print "\t%s (%s, %s)" % ( port, desc, hwid )
			self.error(str(e))
		except ValueError as e:
			self.error(str(e))

		return gsm

	def _average(self, sens, n):
		readings = []
		for i in xrange(0, n):
			v = sens.read_voltage()
			readings.append(v)

		return sum(readings)/len(readings)

def main():
	sensortool = SensorTool()
	return sensortool.main()