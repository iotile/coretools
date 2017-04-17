import pytest
from pkg_resources import resource_filename, Requirement
import iotile.build.utilities.template as template


@pytest.fixture
def qemu_template():
    return 'qemu_semihost_unit', resource_filename(Requirement.parse("iotile-build"), "iotile/build/config/templates")


def test_output_file_iteration(qemu_template):
    """Make sure output file iteration works."""

    temp = template.RecursiveTemplate(*qemu_template)

    outfiles = [x for x in temp.iter_output_files()]

    assert len(outfiles) == 9
    assert 'main.c.tpl' in outfiles


def test_extension_removal(qemu_template):
    """Make sure output file iteration works."""

    temp = template.RecursiveTemplate(*qemu_template, only_ext='.tpl', remove_ext=True)

    outfiles = [x for x in temp.iter_output_files()]

    assert len(outfiles) == 9
    assert 'main.c' in outfiles
