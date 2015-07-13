from pymomo.commander import transport, cmdstream
from pymomo.commander.proxy import *
from pymomo.commander.exceptions import *
from pymomo.utilities.console import ProgressBar
from pymomo.hex16.convert import *
from time import sleep
from tempfile import *
import os
import sys


def reflash_module(controller, hexfile, name=None, address=None, force=False, verbose=True, noreset=False):
	"""
	Given a controller instance, reflash a pic12 application module
	given either its address or name.
	"""

	#Make sure the module exists before pushing the firmware
	mod = controller.get_module(name, address, force)

	controller.clear_firmware_cache()
	bucket = controller.push_firmware(hexfile, 0, verbose=verbose)

	mod.rpc(0, 5, 8, bucket)
	mod.reset()

	sleep(1.5)
	if not controller.alarm_asserted():
		print "Module reflash NOT DETECTED.  Verify the module checksum to ensure it is programmed correctly."
		raise RuntimeError("Could not reflash module, reflash not detected using alarm pin.")

	print "Reflash in progress"
	while controller.alarm_asserted():
		sys.stdout.write('.')
		sys.stdout.flush()
		sleep(0.1)

	print "\nReflash complete."

	sleep(0.5)

	if not noreset: 
		if verbose:
			print "Resetting the bus..."

		controller.reset(sync=True)

