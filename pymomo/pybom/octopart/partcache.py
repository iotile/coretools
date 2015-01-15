#partcache.py
#A simple expiring cache built on top of zodb

import sys
import os.path

from pymomo.utilities.paths import MomoPaths
from ZODB.FileStorage import FileStorage
from ZODB.DB import DB
from time import time
import transaction

class PartCache(object):
	URL = 'http://octopart.com/api/v3/'
	CachePath = os.path.join(MomoPaths().config, 'part_lookup.cache')
	DefaultExpiry = 10*24*60*60		#Default expiration date is 10 days

	def __init__(self):
		storage = FileStorage(PartCache.CachePath)
		self.db = DB(storage)
		self.connection = self.db.open()
		self.root = self.connection.root()

	def _check_valid(self, obj):
		exp = obj['expiration']

		cur = time()

		if exp > cur:
			return True

		return False

	def get(self, id):
		if id not in self.root:
			return None

		obj = self.root[id]

		if self._check_valid(obj):
			obj['last_used'] = time()
			self.root[id] = obj
			transaction.commit()
			return obj['data']

		#If it's expired, delete it
		del self.root[id]
		return None

	def set(self, id, obj, expire=None):
		if expire is None:
			expire = PartCache.DefaultExpiry

		entry = {}
		entry['expiration'] = time() + expire
		entry['data'] = obj
		entry['last_used'] = time()

		self.root[id] = entry
		transaction.commit() 