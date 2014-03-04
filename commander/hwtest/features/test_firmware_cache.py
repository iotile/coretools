from pymomo.commander.hwtest.fixtures import *
from pymomo.commander.exceptions import *
from intelhex import IntelHex16bit
import random
import os.path

class TestFirmwareCache:
	"""
	Test the firmware cache on the MIB controller, feature 7
	"""

	def _random_hex12(self, tmp, name, size):
		hexf = IntelHex16bit()

		for i in xrange(0, size):
			hexf[i] = random.randint(0, 0x3FFF)

		path = os.path.join(str(tmp), name)
		hexf.write_hex_file(path)

		return path

	def _fill_bucket(self, name, tmpdir, controller):
		modtype = random.randint(0,3)
		
		hexp = self._random_hex12(tmpdir, name, 4096)

		bucket = controller.push_firmware(hexp, modtype, verbose=False)
		readhex = controller.pull_firmware(bucket, verbose=False, pic12=True)

		outpath = os.path.join(str(tmpdir), 'output.hex')
		readhex.write_hex_file(outpath)

		return hexp, outpath

	def test_clear(self, controller):
		controller.clear_firmware_cache()

		res = controller.get_firmware_count()
		assert res['module_buckets'] == 0
		assert res['backup_firmware'] == False
		assert res['controller_firmware'] == False

	@pytest.mark.skipif(True, reason="Test is very slow")
	def test_buckets(self, controller, tmpdir):
		controller.clear_firmware_cache()

		in0, out0 = self._fill_bucket('hex0', tmpdir, controller)
		in1, out1 = self._fill_bucket('hex1', tmpdir, controller)
		in2, out2 = self._fill_bucket('hex2', tmpdir, controller)
		in3, out3 = self._fill_bucket('hex3', tmpdir, controller)

		res = controller.get_firmware_count()
		assert res['module_buckets'] == 4

	def test_info_empty(self, controller):
		controller.clear_firmware_cache()

		with pytest.raises(RPCException):
			controller.get_firmware_info(0)

