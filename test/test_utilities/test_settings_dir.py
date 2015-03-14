from pymomo.utilities import build
from nose.tools import *
import unittest
import os.path
import os
import platform
from pymomo.exceptions import *
from pymomo.utilities.paths import MomoPaths

class TestSettingsDirectory:
	def setUp(self):
		self.paths = MomoPaths()
		self.confdir = os.path.join(os.path.expanduser('~'), '.config')

	def test_settings_dir(self):
		assert os.path.exists(self.paths.settings)

	@unittest.skipIf(platform.system() != 'Linux', 'Linux specific test')
	def test_settings_linix(self):
		settings_dir = os.path.abspath(os.path.join(self.confdir, 'WellDone-MoMo'))

		assert settings_dir == self.paths.settings

	@unittest.skipIf(platform.system() != 'Windows', 'Windows specific test')
	def test_settings_windows(self):
		if 'APPDATA' in os.environ:
			base = os.environ['APPDATA']
		else:
			base = self.confdir

		settings_dir = os.path.abspath(os.path.join(base, 'WellDone-MoMo'))
		assert settings_dir == self.paths.settings

	@unittest.skipIf(platform.system() != 'Darwin', 'Mac OS X specific test')
	def test_settings_darwin(self):

		settings_dir = os.path.abspath(os.path.join(os.path.expanduser('~'), 'Library', 'Preferences',
															'WellDone-MoMo'))

		assert settings_dir == self.paths.settings