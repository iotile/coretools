import unittest
import os.path
import os
from nose.tools import *
from pymomo.exceptions import *
from pymomo.pcb import CircuitBoard
import pymomo.pcb.partcache
import tempfile
import shutil
import atexit
import hashlib

class TestBOMCreation(unittest.TestCase):
	"""
	Test to make sure that BOM matching and BOM generation work.
	"""

	def _create_tempfile(self, src=None):
		"""
		Create a named temporary file that is a copy of the src file
		and register for it to be deleted at program exit.
		"""
		dst = tempfile.NamedTemporaryFile(delete=False)

		if src is not None:
			with open(src, "r+b") as f:
				shutil.copyfileobj(f, dst)

		dst.close()

		atexit.register(os.remove, dst.name)
		return dst.name

	def _hash_file(self, path):
		hasher = hashlib.sha256()

		with open(path,'r') as f:
			block = 2**16 - 1
			buf = f.read(block)
			while len(buf) > 0:
				hasher.update(buf)
				buf = f.read(block)

		return hasher.hexdigest()

	def setUp(self):
		self.srcbrd = self._create_tempfile(os.path.join(os.path.dirname(__file__), 'eagle', 'controller_missing_attrs.brd'))
		cachefile = self._create_tempfile(os.path.join(os.path.dirname(__file__), 'eagle', 'pcb_part_cache.db'))
		
		#Make sure we use our cache file and don't let it expire so we don't delete all of the entries
		pymomo.pcb.partcache.default_cachefile(cachefile)
		pymomo.pcb.partcache.default_noexpire(True)
		self.board = CircuitBoard(self.srcbrd)
		self.board.set_match_engine("CacheOnlyMatcher")

	def tearDown(self):
		pass

	def test_cached_matching(self):
		"""
		Make sure that the cache is working 
		"""

		self.board.match_status()
		print self.board.match_details()

		assert self.board.match_status() == True

	def test_lookup(self):
		part = self.board.lookup('U5')
		assert part is not None

	def test_update_metadata(self):
		self.board.update_metadata('U5')

		board1 = CircuitBoard(self.srcbrd)
		part = board1.find('U5')
		
		print part.mpn
		print part.manu
		print part.desc

		assert part.mpn == 'M25PX80-VMN6TP'
		assert part.manu == 'MICRON'

	def test_update_all_metadata(self):
		self.board.update_all_metadata()

		board1 = CircuitBoard(self.srcbrd)
		
		for part in board1._iterate_parts():
			assert part.mpn is not None
			assert part.manu is not None

	def test_export_excel(self):
		"""
		Make sure that the BOM exporter works for excel files without error
		"""

		output = self._create_tempfile()

		self.board.export_bom(output, format='excel')
		#We can't verify the output with a hash since there's an embedded timestamp
		#in the file format so just make sure it runs without error.

