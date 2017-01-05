import pytest
import os
from iotile.build.dev.depmanager import DependencyManager
from iotile.core.dev.iotileobj import IOTile
from iotile.core.exceptions import ArgumentError,BuildError

def comp_path(name):
    return os.path.join(os.path.dirname(__file__), name)

def get_iotile(name):
	return IOTile(comp_path(name))

def test_dep_version_conflict():
	"""Test to make sure that version conflicts among installed deps are found
	"""

	man = DependencyManager()

	with pytest.raises(BuildError):
		man.ensure_compatible(comp_path('comp5_depconflict'))

def test_dep_version_noconflict():
	man = DependencyManager()
	man.ensure_compatible(comp_path('comp5_noconflict'))

def test_dep_version_notinstalled():
	man = DependencyManager()

	with pytest.raises(ArgumentError):
		man.ensure_compatible(comp_path('comp5_noinstalled'))