"""Tests to ensure that render_template and render_recursive_template work."""

import os.path
import pytest
import shutil
from iotile.build.utilities import render_recursive_template, render_template_inplace


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

    for file in files:
        assert os.path.isfile(os.path.join(out_dir, file))

    for folder in dirs:
        assert os.path.isdir(os.path.join(out_dir, folder))


def test_render_preserve(tmpdir):
    """Make sure we can actually do a recursive render."""

    out_dir = str(tmpdir)
    files, dirs = render_recursive_template('qemu_semihost_unit', {}, out_dir,
                                            preserve=['main.c.tpl'])

    for file in files:
        assert os.path.isfile(os.path.join(out_dir, file))

    for folder in dirs:
        assert os.path.isdir(os.path.join(out_dir, folder))

    assert 'main.c' not in files
    assert 'main.c.tpl' in files

def test_inplace_render(tmpdir):
    """Make sure we can render a single template file in place."""

    inpath = os.path.join(os.path.dirname(__file__), 'data', 'template.c.tpl')

    tmpfile = tmpdir.join('template.c.tpl')
    tmppath = str(tmpfile)
    shutil.copyfile(inpath, tmppath)

    outpath = render_template_inplace(tmppath, {}, dry_run=True)
    assert outpath == tmppath[:-4]
    assert not os.path.exists(outpath)

    outpath = render_template_inplace(tmppath, {})
    assert outpath == tmppath[:-4]
    assert os.path.exists(outpath)
