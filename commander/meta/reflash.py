from pymomo.commander import transport, cmdstream
from pymomo.commander.proxy import *
from pymomo.commander.exceptions import *
from pymomo.utilities.console import ProgressBar
from time import sleep

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
		prog.sleep(10)
