"""Tests to make sure that 'iotile build' works."""

# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

import pytest
import os.path
import os
import shutil
import subprocess
from distutils.spawn import find_executable
from iotile.core.dev.registry import ComponentRegistry
from iotile.core.utilities.intelhex import IntelHex


def copy_folder(local_name, tmpdir):
    """Copy a complete folder by name into a temporary directory."""
    path = os.path.join(os.path.dirname(__file__), local_name)
    if not os.path.isdir(path):
        raise ValueError("%s is not a directory" % local_name)

    outpath = str(tmpdir.join(local_name))
    shutil.copytree(path, outpath)

    return outpath


def test_iotiletool():
    """Make sure the iotile tool works."""
    err = subprocess.check_call(["iotile", "quit"])
    assert err == 0


def test_build_command():
    """Make sure iotile.build has been properly registered as a plugin."""

    reg = ComponentRegistry()
    plugs = reg.list_plugins()
    assert 'build' in plugs


def test_build(tmpdir):
    """Make sure we can build a blank component."""

    olddir = os.getcwd()
    builddir = copy_folder('blank_component', tmpdir)

    try:
        os.chdir(builddir)
        err = subprocess.check_call(["iotile", "build"])
        assert err == 0
    finally:
        os.chdir(olddir)


def test_build_nodepends(tmpdir):
    """Make sure we can build a component with no depends key."""

    olddir = os.getcwd()
    builddir = copy_folder('component_nodependskey', tmpdir)

    try:
        os.chdir(builddir)
        err = subprocess.check_call(["iotile", "build"])
        assert err == 0
    finally:
        os.chdir(olddir)


def test_build_with_python_depends(tmpdir):
    """Make sure we can build a component with a python package dependency"""
    olddir = os.getcwd()
    builddir = copy_folder('component_pythondepends', tmpdir)

    try:
        os.chdir(builddir)
        err = subprocess.check_call(["iotile", "build"])
        assert err == 0
    finally:
        os.chdir(olddir)


def test_build_arm(tmpdir):
    """Make sure we can build a component with no depends key."""

    olddir = os.getcwd()
    builddir = copy_folder('arm_component', tmpdir)

    try:
        os.chdir(builddir)
        err = subprocess.check_call(["iotile", "build"])
        assert err == 0
    finally:
        os.chdir(olddir)


def test_build_python(tmpdir):
    """Make sure we can build a component with a full python distribution."""

    olddir = os.getcwd()
    builddir = copy_folder('python_component', tmpdir)

    try:
        os.chdir(builddir)
        err = subprocess.check_call(["iotile", "build"])
        assert err == 0
    finally:
        os.chdir(olddir)


def test_build_prerelease(tmpdir):
    """Make sure we can build a component with no depends key."""

    olddir = os.getcwd()
    builddir = copy_folder('prerelease_component', tmpdir)

    try:
        os.chdir(builddir)
        err = subprocess.check_call(["iotile", "build"])
        assert err == 0
    finally:
        os.chdir(olddir)

@pytest.mark.skipif(find_executable('qemu-system-gnuarmeclipse') is None, reason="qemu emulator not installed")
def test_unit_testing(tmpdir):
    """Make sure we can build and run unit tests."""

    olddir = os.getcwd()
    builddir = copy_folder('comp_with_tests', tmpdir)

    try:
        os.chdir(builddir)
        err = subprocess.check_call(["iotile", "build", "build/test"])
        assert err == 0
    finally:
        os.chdir(olddir)


def test_bootstrap_file(tmpdir):
    """Make sure we can create a bootstrap file"""
    olddir = os.getcwd()
    builddir = copy_folder('component_bootstrap', tmpdir)

    try:
        os.chdir(builddir)

        print os.listdir(os.path.join('build', 'output', builddir))

        hexdata = IntelHex(os.path.join('build', 'output', 'test1.hex'))
        assert hexdata.segments() == [(0x10001014, 0x10001018)]

        assert not os.path.isfile(os.path.join('build', 'output', 'test2.hex'))

        err = subprocess.check_call(["iotile", "build"])
        assert err == 0

        hexdata = IntelHex(os.path.join('build', 'output', 'test_final.hex'))
        hexdata_dup = IntelHex(os.path.join('build', 'output', 'test_final_dup.hex'))
        assert hexdata.segments() == hexdata_dup.segments()
    finally:
        os.chdir(olddir)
