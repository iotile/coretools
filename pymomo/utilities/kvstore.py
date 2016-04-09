#Sqlite3 textual key value store
from pymomo.utilities.paths import MomoPaths
import sqlite3
import os.path

class KeyValueStore(object):
	"""
	A simple string - string persistent map backed by sqlite
	"""

	DefaultFolder = os.path.join(MomoPaths().settings)

	def __init__(self, name, folder=None):
		if folder is None:
			folder = KeyValueStore.DefaultFolder

		dbfile = os.path.join(folder, name)
		self.connection = sqlite3.connect(dbfile)
		self.cursor = self.connection.cursor()

		self.file = dbfile
		self._setup_table()

	def _setup_table(self):
		query = 'create table if not exists KVStore (key TEXT PRIMARY KEY, value TEXT);'
		self.cursor.execute(query)
		self.connection.commit()

	def size(self):
		query = 'select count(*) from KVStore'
		self.cursor.execute(query)
		return self.cursor.fetchone()[0]

	def get(self, id):
		query = 'select value from KVStore where key is ?'
		self.cursor.execute(query, (id,))

		val = self.cursor.fetchone()
		if val is None:
			raise KeyError("id not in key-value store: %s" % str(id))
		
		return val[0]

	def remove(self, key):
		query = "delete from KVStore where key is ?"
		self.cursor.execute(query, (key,))
		self.connection.commit()

	def try_get(self, id):
		try:
			return self.get(id)
		except KeyError:
			return None

	def set(self, key, value):
		query = "insert or replace into KVStore values (?, ?)"
		self.cursor.execute(query, (key, str(value)))
		self.connection.commit()

	def clear(self):
		query = 'drop table KVStore'
		self.cursor.execute(query)
		self.connection.commit()

		self._setup_table()
