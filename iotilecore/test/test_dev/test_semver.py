from iotile.core.dev.iotileobj import SemanticVersion
from iotile.core.exceptions import DataError
import pytest

def test_basic_parsing():
    ver1 = SemanticVersion.FromString('1.2.3')

    assert ver1.major == 1 and ver1.minor == 2 and ver1.patch == 3
    assert ver1.release_type == 'release'
    assert ver1.is_release is True
    assert ver1.is_prerelease is False

def test_prerelease_parsing():
    reltype, relnum = SemanticVersion.ParsePrerelease('alpha1')

    assert reltype == 'alpha'
    assert relnum == 1

    reltype, relnum = SemanticVersion.ParsePrerelease('beta10')
    assert reltype == 'beta'
    assert relnum == 10

    reltype, relnum = SemanticVersion.ParsePrerelease('rc20')
    assert reltype == 'rc'
    assert relnum == 20

    reltype, relnum = SemanticVersion.ParsePrerelease('build30')
    assert reltype == 'build'
    assert relnum == 30

    with pytest.raises(DataError):
        SemanticVersion.ParsePrerelease('30')

    with pytest.raises(DataError):
        SemanticVersion.ParsePrerelease('build')

    with pytest.raises(DataError):
        SemanticVersion.ParsePrerelease('unknown5')

    with pytest.raises(DataError):
        SemanticVersion.ParsePrerelease('unknown')

    with pytest.raises(DataError):
        SemanticVersion.ParsePrerelease('')

def test_advanced_parsing():
    ver = SemanticVersion.FromString('0.1.2-alpha2')
    assert ver.major == 0
    assert ver.minor == 1
    assert ver.patch == 2
    assert ver.is_prerelease is True
    assert ver.release_type == 'alpha'
    assert ver.prerelease_number == 2

def test_equality():
    ver1 = SemanticVersion.FromString('0.1.2-alpha2')
    ver2 = SemanticVersion.FromString('0.1.2-alpha2')

    assert ver1 == ver2
    assert not ver1 < ver2

def test_ordering_release_over_pre():
    ver1 = SemanticVersion.FromString('0.1.2')
    ver2 = SemanticVersion.FromString('0.1.2-rc1')

    assert ver2 < ver1
    assert ver1 > ver2

def test_ordering_prereleases():
    build = SemanticVersion.FromString('0.1.2-build10')
    alpha = SemanticVersion.FromString('0.1.2-alpha9')
    beta = SemanticVersion.FromString('0.1.2-beta8')
    rc = SemanticVersion.FromString('0.1.2-rc7')
    bump = SemanticVersion.FromString('0.1.3-build1')

    assert build < alpha < beta < rc < bump

def test_ordering_releases():
    major = SemanticVersion.FromString('1.0.0')
    minor = SemanticVersion.FromString('0.9.0')
    patch = SemanticVersion.FromString('0.8.9')

    assert patch < minor < major
