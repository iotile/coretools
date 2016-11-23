from iotilebuild.build.build import ArchitectureGroup
import os

comp_file = os.path.join(os.path.dirname(__file__), 'component', 'module_settings.json')

def test_resolvedeps():
	groups = ArchitectureGroup(comp_file)

	archs = groups.archs.keys()

	assert 'lpc824' in archs
	assert len(archs) == 1
