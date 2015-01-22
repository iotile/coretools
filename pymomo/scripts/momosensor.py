import sys
import os.path
import os
from random import randint

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pymomo.commander.meta import *
from pymomo.commander.exceptions import *
import cmdln

import sched, time

class MoMoSensor(cmdln.Cmdln):
	name = 'MoMoSensor'

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_emulate(self, subcmd, opts, sensor_address):
		"""${cmd_name}: Log a random (1-1000) sensor value every .1 seconds

		${cmd_usage}
		${cmd_option_list}
		"""
		
		con = self._get_controller(opts)

		meta = 0x0;
		s = sched.scheduler(time.time, time.sleep)
		def log_event( scheduler ):
			s.enter( 1, 1, log_event, (scheduler,) )
			value = randint(1,1000)
			con.sensor_log( int(sensor_address), int(meta), value )
			print "Logged event!  Value: %d" % value

		s.enter( 1, 1, log_event, (s,) )
		s.run()

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_test(self, subcmd, opts):
		"""${cmd_name}: Test subsection bound overflow

		${cmd_usage}
		${cmd_option_list}
		"""
		
		con = self._get_controller(opts)

		meta = 0x0;
		s = sched.scheduler(time.time, time.sleep)
		def log_event( scheduler, count, values ):
			memory_subsection_count = 16 * 12 - 1
			events_per_subsection = 341 # 4096/12
			if count >= events_per_subsection*memory_subsection_count + 10: # = when to stop
				print "COMPLETE"
				debug = con.sensor_log_debug()
				print "DEBUG ADDRESSES: MIN %d, MAX %d, START %d, END %d" % con.sensor_log_debug()
				print "Try reading past the end..."
				while len(values) > 0: #should be 351 at this point, read past the end of the buffer to test wrapping.

					v = con.sensor_log_read().value
					ev = values.pop(0)
					if v != ev:
						print "FAILED: %d != %d (expected)" % ( v, ev )
						return
					else:
						print "(%d) read %d" % (len(values), v)
					
					if len(values) != con.sensor_log_count():
						print "FAILED"
						print "count: %d, expected: %d" % (con.sensor_log_count(), len(values))
						print "DEBUG ADDRESSES: MIN %d, MAX %d, START %d, END %d" % con.sensor_log_debug()
						return
				print "SUCCESS"
				print "DEBUG ADDRESSES: MIN %d, MAX %d, START %d, END %d" % con.sensor_log_debug()
				return

			if ( len(values) > events_per_subsection*memory_subsection_count ):
				for i in range(events_per_subsection):
					values.pop(0)
			if ( len(values) != con.sensor_log_count() ):
				print "FAILURE"
				print "count: %d, expected: %d" % (con.sensor_log_count(), len(values))
				print "DEBUG ADDRESSES: MIN %d, MAX %d, START %d, END %d" % con.sensor_log_debug()
				return

			value = randint(1,1000)
			values.append(value)
			con.sensor_log( 42, int(meta), value )
			print "(%d) Logged event!  Value: %d" % (len(values), value)
			s.enter( .01, 1, log_event, (scheduler,count+1,values) )

		con.sensor_log_clear()
		print "All sensor events cleared from PIC memory."
		values = []
		s.enter( .1, 1, log_event, (s,0,values) )
		s.run()

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_readone(self, subcmd, opts):
		"""${cmd_name}: Read one event from the log.

		${cmd_usage}
		${cmd_option_list}
		"""
		
		con = self._get_controller(opts)
		event = con.sensor_log_read()

		print "Stream: %d" % event.stream
		print "MetaData: %d" % event.metadata
		print "Timestamp: %s" % str( event.timestamp )
		print "Value: %d" % event.value

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_log(self, subcmd, opts, sensor_address, meta, value):
		"""${cmd_name}: Log one integer value (32-bit)

		${cmd_usage}
		${cmd_option_list}
		"""
		con = self._get_controller(opts)
		con.sensor_log( int(sensor_address), int(meta), int(value) )
		print "Logged event!"

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_count(self, subcmd, opts):
		"""${cmd_name}: Number of events in the sensor log.

		${cmd_usage}
		${cmd_option_list}
		"""
		con = self._get_controller(opts)
		print con.sensor_log_count();

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_clear(self, subcmd, opts):
		"""${cmd_name}: Clear all values from the sensor log, resetting the pointers to
		  the beginning of the flash_queue.

		${cmd_usage}
		${cmd_option_list}
		"""
		con = self._get_controller(opts)
		con.sensor_log_clear();
		print "All sensor events cleared from PIC memory."

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	def do_debug(self, subcmd, opts):
		"""${cmd_name}: Print out the min, max, start, and end addresses

		${cmd_usage}
		${cmd_option_list}
		"""
		
		con = self._get_controller(opts)

		print "DEBUG ADDRESSES: MIN %d, MAX %d, START %d, END %d" % con.sensor_log_debug()

	def _get_controller(self, opts):
		try:
			c = get_controller(opts.port)
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

		return c

def main():
	emulator = MoMoSensor()
	return emulator.main()