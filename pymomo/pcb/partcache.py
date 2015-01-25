#partcache.py
#A simple expiring cache built on top of sqlite

import sys
import os.path

from pymomo.utilities.paths import MomoPaths
from time import time
import sqlite3
import cPickle

overriden_cache = None
overriden_expiry = None

class PartCache(object):
	"""
	A simple persistent key-value store with expiration times

	Persistence comes from a sqlite backend and each time the 
	file is opened, all entries are checked to see if they should
	be expired and deleted if so.
	"""

	DefaultCachePath = os.path.join(MomoPaths().settings, 'pcb_part_cache.db')
	DefaultExpiry = 1*24*60*60		#Default expiration date is 1 day

	def __init__(self, cache=None, no_expire=None, expiration=None):
		if cache is None:
			if overriden_cache is not None:
				cache = overriden_cache
			else:
				cache = PartCache.DefaultCachePath

		if expiration is None:
			expiration = PartCache.DefaultExpiry
		else:
			expiration = int(expiration)

		self.connection = sqlite3.connect(cache)
		self.cursor = self.connection.cursor()

		self.file = cache
		self.expiration = expiration

		self._setup_table()

		if no_expire is None:
			if overriden_expiry is None or overriden_expiry is False:
				self._expire_old()
		elif not no_expire:
			self._expire_old()

	def _setup_table(self):
		query = 'create table if not exists PartCache (key TEXT PRIMARY KEY, created INTEGER, part blob);'
		self.cursor.execute(query)
		self.connection.commit()

	def _expire_old(self):
		query = "delete from PartCache where strftime('%%s','now') - created > %d" % self.expiration
		self.cursor.execute(query)
		self.connection.commit()

		return self.cursor.rowcount

	def size(self):
		"""
		Return the number of entries in this cache
		"""

		query = 'select count(*) from PartCache'
		self.cursor.execute(query)
		return self.cursor.fetchone()[0]

	def _check_valid(self, obj):
		exp = obj['expiration']

		cur = time()

		if exp > cur:
			return True

		return False

	def get(self, id):
		query = 'select part from PartCache where key is ?'
		self.cursor.execute(query, (id,))

		val = self.cursor.fetchone()
		if val is None:
			raise KeyError("id not in cache: %s", str(id))
		
		return cPickle.loads(str(val[0]))

	def try_get(self, id):
		try:
			return self.get(id)
		except KeyError:
			return None

	def set(self, id, obj):
		now = time()
		data = cPickle.dumps(obj)

		query = "insert into PartCache values (?, strftime('%s','now'), ?)"
		self.cursor.execute(query, (id, sqlite3.Binary(data)))
		self.connection.commit()


def default_cachefile(path):
	"""
	Set the default cache file used to back PartCache objects
	"""

	global overriden_cache
	overriden_cache = path

def default_noexpire(do_expire):
	"""
	Set whether cache should not expire by default
	"""

	global overriden_expiry
	overriden_expiry = do_expire
