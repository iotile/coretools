from iotile.build.build.build import ArchitectureGroup
import os

comp_file = os.path.join(os.path.dirname(__file__), 'component', 'module_settings.json')

def test_resolvedeps():
    groups = ArchitectureGroup(comp_file)

    archs = list(groups.archs)
    assert 'lpc824' in archs
    assert 'none' in archs
    assert len(archs) == 2
