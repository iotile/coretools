# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import unittest
import os.path
import os
from nose.tools import *
from nose.plugins.skip import SkipTest
from iotilecore.exceptions import *
from iotilecore.pcb import CircuitBoard
from iotilecore.pcb.production import ProductionFileGenerator
from distutils.spawn import find_executable
import iotilecore
import tempfile
import shutil
import atexit

class TestProductionFileGeneration(unittest.TestCase):
	"""
	Test to make sure that BOM matching and BOM generation work.
	"""

	def _create_tempfile(self, src=None, ext=None):
		"""
		Create a named temporary file that is a copy of the src file
		and register for it to be deleted at program exit.
		"""
		dst = tempfile.NamedTemporaryFile(delete=False)

		if src is not None:
			with open(src, "r+b") as f:
				shutil.copyfileobj(f, dst)

		dst.close()

		name = dst.name
		if ext is not None:
			name = dst.name+"." + ext
			os.rename(dst.name, name)

		atexit.register(os.remove, name)
		return name

	def _create_tempdir(self):
		path = tempfile.mkdtemp()
		atexit.register(shutil.rmtree, path)
		return path

	def setUp(self):
		self.srcbrd = self._create_tempfile(os.path.join(os.path.dirname(__file__), 'eagle', 'controller_complete.brd'), ext='brd')
		cachefile = self._create_tempfile(os.path.join(os.path.dirname(__file__), 'eagle', 'pcb_part_cache.db'))
		
		#Make sure we use our cache file and don't let it expire so we don't delete all of the entries
		iotilecore.pcb.partcache.default_cachefile(cachefile)
		iotilecore.pcb.partcache.default_noexpire(True)
		self.board = CircuitBoard(self.srcbrd)
		self.board.set_match_engine("CacheOnlyMatcher")

	def tearDown(self):
		pass

	def test_basic(self):
		"""
		Basic tests of ProductionFileGenerator
		"""

		prod = ProductionFileGenerator(self.board)
		prod.save_readme(self._create_tempfile())

	def test_prod(self):
		try:
			eagle = self.board.board._find_eagle()
		except EnvironmentError:
			raise SkipTest("Eagle could not be found")

		print eagle

		out = self._create_tempdir()
		self.board.generate_production(out)
