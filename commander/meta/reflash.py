from pymomo.commander import transport, cmdstream
from pymomo.commander.proxy import *
from pymomo.commander.exceptions import *
from pymomo.utilities.console import ProgressBar
from pymomo.hex16.convert import *
from time import sleep
from tempfile import *
import os
import sys


def reflash_module(controller, hexfile, name=None, address=None, force=False, verbose=True):
	"""
	Given a controller instance, reflash a pic12 application module
	given either its address or name.
	"""

	#Make sure the module exists before pushing the firmware
	mod = controller.get_module(name, address, force)

	controller.clear_firmware_cache()
	bucket = controller.push_firmware(hexfile, 0, verbose=verbose)

	mod.rpc(1, 0, 8, bucket)
	mod.reset()

	if verbose:
		prog = ProgressBar("Reflashing", 10)
		prog.start()

		for i in xrange(0, 10):
			sleep(1)
			prog.progress(i)

		prog.end()
	else:
		sleep(10)

	if verbose:
		print "Resetting the bus..."

	controller.reset(sync=True)

	if verbose:
		print "Reflash complete"

def _convert_hex24(hexfile):
	tmpf = NamedTemporaryFile(delete=False)
	tmpf.close()

	tmp = tmpf.name

	out = unpad_pic24_hex(hexfile)
	out.write_hex_file(tmp)
	return tmp

def reflash_controller(controller, hexfile, verbose=True):
	"""
	Given a path to a hexfile, push it onto the controller and then
	tell the controller to reflash itself.
	"""

	processed = _convert_hex24(hexfile)
	controller.push_firmware(processed, 5, verbose=verbose)
	os.remove(processed)
	controller.reflash()

	sleep(0.5)
	if not controller.alarm_asserted():
		print "Controller reflash NOT DETECTED.  You may need to try the recovery procedure."
		raise RuntimeError("Could not reflash controller")

	print "Reflash in progress"
	while controller.alarm_asserted():
		sys.stdout.write('.')
		sys.stdout.flush()
		sleep(0.1)

	print "\nReflash complete."
