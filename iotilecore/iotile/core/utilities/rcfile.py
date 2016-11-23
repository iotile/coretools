# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#rcfile.py
#A simple way to store and access configuration files in a cross-platform way.
#It uses dirspec to find the appropriate config directory for each platform and
#then creates a file under that directory with the appropriate application name

import os.path
from paths import settings_directory
from iotile.core.exceptions import *

class RCFile:
	"""
	A simple object that represents a configuration file stored in a cross-platform
	way by looking for the appropriate configuration directory on each platform.  The 
	file is named NAME_config.txt and its contents are accessible via the .contents
	attribute of the class.
	"""

	def __init__(self, name):
		"""
		Access the configuration file for the configurable object name.  Multiple calls
		with the same name string will return the same configuration file.
		"""

		self.name = name
		self.path = self._build_path()
		self.valid= True
		self.error = ""

		#Read in the file ignoring all blank lines and chopping off newline characters
		try:
			with open(self.path, "r") as f:
				contents = f.readlines()

			self.contents = [x.rstrip() for x in contents if len(x.rstrip()) > 0]
		except IOError as e:
			self.valid = False
			self.error = str(e)
			self.contents = []

	def _build_path(self):		
		fname = "%s_config.txt" % self.name

		return os.path.join(settings_directory(), fname)

	def save(self):
		"""
		Update the configuration file on disk with the current contents of self.contents.
		Previous contents are overwritten.
		"""

		try:
			with open(self.path, "w") as f:
				f.writelines(self.contents)
		except IOError as e:
			raise InternalError("Could not write RCFile contents", name=self.name, path=self.path, error_message=str(e))
