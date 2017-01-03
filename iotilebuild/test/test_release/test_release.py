import pytest
import os
import subprocess

def test_iotiletool():
    err = subprocess.check_call(["iotile" , "quit"])
    assert err == 0

from iotile.build.release.release import release, DirtyReleaseFailureError, CleanReleaseFailureError
from iotile.core.exceptions import DataError, ArgumentError

def build_path(name):
    parent = os.path.dirname(__file__)
    path = os.path.join(parent, name)

    return path

def test_successful_release():
    comp = build_path('successful_release_comp')

    release(comp)

def test_failed_stage1():
    """Make sure appropriate error is thrown when staging fails

    Also test to make sure unstage happens correctly
    """

    comp = build_path('fail_first_stage_comp')

    with pytest.raises(CleanReleaseFailureError):
        try:
            release(comp)
        except CleanReleaseFailureError, exc:
            assert exc.params['failed_step'] == 0
            assert exc.params['operation'] == 'staging'
            raise

def test_failed_stage2():
    """Make sure appropriate dirty error is thrown if staging fails and cannot roll back
    """

    comp = build_path('fail_second_stage_comp')

    with pytest.raises(DirtyReleaseFailureError):
        try:
            release(comp)
        except DirtyReleaseFailureError, exc:
            assert exc.params['failed_step'] == 1
            assert exc.params['failed_unstage'] == 0
            assert exc.params['operation'] == 'staging'

            raise

def test_failed_release1():
    """Make sure appropriate error is thrown when release fails

    Also test to make sure unrelease happens correctly
    """

    comp = build_path('fail_first_release_comp')

    with pytest.raises(CleanReleaseFailureError):
        try:
            release(comp)
        except CleanReleaseFailureError, exc:
            assert exc.params['failed_step'] == 0
            assert exc.params['operation'] == 'release'
            raise

def test_failed_release2():
    """Make sure appropriate dirty error is thrown if releasing fails and cannot roll back
    """

    comp = build_path('fail_second_release_comp')

    with pytest.raises(DirtyReleaseFailureError):
        try:
            release(comp)
        except DirtyReleaseFailureError, exc:
            assert exc.params['failed_step'] == 1
            assert exc.params['failed_unrelease'] == 0
            assert exc.params['operation'] == 'release'

            raise

def test_built_devmode_comp():
    """Make sure that if a devmode comp has been built we release the build/output folder
    """

    comp = build_path('dev_mode_comp')
    release(comp)

def test_unbuilt_devmode_comp():
    """Make sure that we throw an error if we try to release an unbuilt dev mode component
    """

    comp = build_path('unbuilt_dev_mode_comp')
    
    with pytest.raises(ArgumentError):
        release(comp)

def test_nosteps_comp():
    """Make sure that if there are no release steps we throw an error
    """

    comp = build_path('nosteps_comp')
    
    with pytest.raises(ArgumentError):
        release(comp)


def test_unknown_provider():
    """Make sure that we get the appropriate error if a ReleaseProvider cannot be found
    """

    comp = build_path('unknown_provider_comp')

    with pytest.raises(DataError):
        release(comp)

def test_release_plugin():
    """Makes sure the release plugin works correctly in the iotile tool
    """

    err = subprocess.check_call(["iotile" , "release", build_path('successful_release_comp')])
    assert err == 0
