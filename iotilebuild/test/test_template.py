"""Tests to ensure that render_template and render_recursive_template work."""

import os.path
import pytest
from iotile.build.utilities import render_recursive_template


def test_dryrun():
    """Make sure we can get a good list of all output files."""

    files, dirs = render_recursive_template('qemu_semihost_unit', {}, "output_folder", dry_run=True)

    print(files)
    assert len(files) == 9
    assert len(dirs) == 0

    # Make sure .tpl is stripped
    assert files['main.c'][0] == 'main.c.tpl'

def test_recursive_render(tmpdir):
    """Make sure we can actually do a recursive render."""

    out_dir = str(tmpdir)
    files, dirs = render_recursive_template('qemu_semihost_unit', {}, out_dir)

    for file in files.iterkeys():
        assert os.path.isfile(os.path.join(out_dir, file))

    for folder in dirs:
        assert os.path.isdir(os.path.join(out_dir, folder))
