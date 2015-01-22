#!/usr/bin/env python

import sys, os

from pymomo.commander.meta import *
from pymomo.commander.exceptions import *
from pymomo.commander.proxy import *

import cmdln

class GSMTool(cmdln.Cmdln):
	name = 'gsmtool'

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-a', '--address', help='The MIB address of the GSM module' )
	def do_on(self, subcmd, opts):
		"""${cmd_name}: Turn on the GSM modem.

		${cmd_usage}
		${cmd_option_list}
		"""
		gsm = self._create_proxy( opts )
		if gsm.module_on(): 
			print "OK"
		else:
			print "ERROR"

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-a', '--address', help='The MIB address of the GSM module' )
	def do_off(self, subcmd, opts):
		"""${cmd_name}: Turn off the GSM modem

		${cmd_usage}
		${cmd_option_list}
		"""
		gsm = self._create_proxy( opts )
		gsm.module_off()

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-a', '--address', help='The MIB address of the GSM module' )
	def do_dump(self, subcmd, opts):
		"""${cmd_name}: Dump the modem's serial buffer (for debugging)

		${cmd_usage}
		${cmd_option_list}
		"""
		gsm = self._create_proxy( opts )
		res = gsm.dump_buffer()
		print "(%d): %s" % (len(res), res)

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-a', '--address', help='The MIB address of the GSM module' )
	def do_debug(self, subcmd, opts):
		"""${cmd_name}: Get debug info

		${cmd_usage}
		${cmd_option_list}
		"""
		gsm = self._create_proxy( opts )
		res = gsm.debug()
		print "module_on: %s" % bool(ord(res[0]))
		print "shutdown_pending: %s" % bool(ord(res[1]))
		print "rx_buffer_start: %d" % ord(res[2])
		print "rx_buffer_end: %d" % ord(res[3])
		print "debug_val: %d" % ord(res[4])

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-a', '--address', help='The MIB address of the GSM module' )
	def do_cmd(self, subcmd, opts, cmd):
		"""${cmd_name}: Tell the GSM modem to execute an AT command

		${cmd_usage}
		${cmd_option_list}
		"""
		gsm = self._create_proxy( opts )
		res = gsm.at_cmd( cmd )
		print res

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-a', '--address', help='The MIB address of the GSM module' )
	def do_msg(self, subcmd, opts, dest, text ):
		"""${cmd_name}: Send a text message with the content <text> to <dest>

		${cmd_usage}
		${cmd_option_list}
		"""
		gsm = self._create_proxy( opts )
		#gsm.module_on();
		res = gsm.send_text( dest, text );
		#gsm.module_off();

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-a', '--address', help='The MIB address of the GSM module' )
	def do_apn(self, subcmd, opts, apn ):
		"""${cmd_name}: Set the GPRS APN

		${cmd_usage}
		${cmd_option_list}
		"""
		gsm = self._create_proxy( opts )
		gsm.set_apn(apn);
		print "OK"

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-a', '--address', help='The MIB address of the GSM module' )
	def do_gprs(self, subcmd, opts ):
		"""${cmd_name}: Test GPRS functionality

		${cmd_usage}
		${cmd_option_list}
		"""
		gsm = self._create_proxy( opts )
		res = gsm.test_gprs();
		print res

	@cmdln.option('-p', '--port', help='Serial port that fsu is plugged into')
	@cmdln.option('-a', '--address', help='The MIB address of the GSM module' )
	def do_simtest(self, subcmd, opts ):
		"""${cmd_name}: Test that a SIM card is inserted

		${cmd_usage}
		${cmd_option_list}
		"""
		gsm = self._create_proxy( opts )
		res = gsm.rpc(10,3,result_type=(1, False));
		print res['ints'][0] != 0

	def _create_proxy(self,opts):
		try:
			con = get_controller(opts.port)
			address = 11
			if opts.address != None:
				address = opts.address
			gsm = GSMModule(con.stream, address)
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

def main():
	gsmtool = GSMTool()
	return gsmtool.main()