#reference.py
#Object to store and retrieve common include directories

import utilities

class Reference:
	def __init__(self):
		conf = utilities.load_settings()

		self.ref = conf['reference']