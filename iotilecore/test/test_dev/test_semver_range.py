"""Tests for SemanticVersion and SemanticVersionRange classes."""

from iotile.core.dev.semver import SemanticVersion, SemanticVersionRange
from iotile.core.exceptions import ArgumentError
import pytest


def test_basic_parsing_exceptions():
    """Make sure we throw the righ parsing errors."""

    with pytest.raises(ArgumentError):
        SemanticVersionRange.FromString('')

    with pytest.raises(ArgumentError):
        SemanticVersionRange.FromString(' ')


def test_star():
    """Make sure wildcard matching works."""

    ver_range = SemanticVersionRange.FromString('*')

    ver = SemanticVersion.FromString('1.0.0')
    ver2 = SemanticVersion.FromString('0.0.1-alpha1')

    assert ver_range.check(ver)
    assert ver_range.check(ver2)


def test_equals():
    """Make sure =X.Y.Z version ranges work."""

    ver_range = SemanticVersionRange.FromString('=0.0.1')
    assert ver_range.check(SemanticVersion.FromString('0.0.1'))
    assert not ver_range.check(SemanticVersion.FromString('0.0.1-alpha2'))
    assert not ver_range.check(SemanticVersion.FromString('0.0.2'))
    assert not ver_range.check(SemanticVersion.FromString('0.1.1'))
    assert not ver_range.check(SemanticVersion.FromString('1.0.1'))

    ver_range = SemanticVersionRange.FromString('=0.1.1')
    assert ver_range.check(SemanticVersion.FromString('0.1.1'))
    assert not ver_range.check(SemanticVersion.FromString('0.1.1-alpha2'))
    assert not ver_range.check(SemanticVersion.FromString('0.2.1'))
    assert not ver_range.check(SemanticVersion.FromString('0.1.0'))
    assert not ver_range.check(SemanticVersion.FromString('1.1.1'))

    ver_range = SemanticVersionRange.FromString('=1.1.1')
    assert ver_range.check(SemanticVersion.FromString('1.1.1'))
    assert not ver_range.check(SemanticVersion.FromString('1.1.1-alpha2'))
    assert not ver_range.check(SemanticVersion.FromString('0.0.2'))
    assert not ver_range.check(SemanticVersion.FromString('0.1.1'))
    assert not ver_range.check(SemanticVersion.FromString('1.2.1'))

    ver_range = SemanticVersionRange.FromString('=1.1.1-alpha2')
    assert ver_range.check(SemanticVersion.FromString('1.1.1-alpha2'))
    assert not ver_range.check(SemanticVersion.FromString('1.1.1-alpha3'))
    assert not ver_range.check(SemanticVersion.FromString('1.1.1'))
    assert not ver_range.check(SemanticVersion.FromString('0.1.1'))
    assert not ver_range.check(SemanticVersion.FromString('1.0.1'))


def test_carrot():
    """Make sure semantic version operator works ^X.Y.Z."""

    ver_range = SemanticVersionRange.FromString('^0.0.1')

    print "Lower: %s" % ver_range._disjuncts[0][0][0]
    print "Upper: %s" % ver_range._disjuncts[0][0][1]

    assert ver_range.check(SemanticVersion.FromString('0.0.1'))
    assert not ver_range.check(SemanticVersion.FromString('0.0.2'))
    assert not ver_range.check(SemanticVersion.FromString('0.1.0'))
    assert not ver_range.check(SemanticVersion.FromString('0.0.2-alpha2'))
    assert not ver_range.check(SemanticVersion.FromString('1.0.0'))

    ver_range = SemanticVersionRange.FromString('^0.1.0')

    print "Lower: %s" % ver_range._disjuncts[0][0][0]
    print "Upper: %s" % ver_range._disjuncts[0][0][1]

    assert ver_range.check(SemanticVersion.FromString('0.1.0'))
    assert ver_range.check(SemanticVersion.FromString('0.1.1'))
    assert not ver_range.check(SemanticVersion.FromString('1.1.0'))
    assert not ver_range.check(SemanticVersion.FromString('0.1.1-alpha2'))
    assert not ver_range.check(SemanticVersion.FromString('1.0.0'))

    ver_range = SemanticVersionRange.FromString('^2.0.0')

    print "Lower: %s" % ver_range._disjuncts[0][0][0]
    print "Upper: %s" % ver_range._disjuncts[0][0][1]

    assert ver_range.check(SemanticVersion.FromString('2.0.0'))
    assert ver_range.check(SemanticVersion.FromString('2.1.1'))
    assert ver_range.check(SemanticVersion.FromString('2.0.1'))
    assert not ver_range.check(SemanticVersion.FromString('2.0.1-alpha1'))
    assert not ver_range.check(SemanticVersion.FromString('1.1.0'))
    assert not ver_range.check(SemanticVersion.FromString('0.1.1-alpha2'))
    assert not ver_range.check(SemanticVersion.FromString('1.0.0'))

    #Make sure prerelease checking works in lower bound
    ver_range = SemanticVersionRange.FromString('^2.0.0-alpha2')

    print "Lower: %s" % ver_range._disjuncts[0][0][0]
    print "Upper: %s" % ver_range._disjuncts[0][0][1]

    assert ver_range.check(SemanticVersion.FromString('2.0.0'))
    assert ver_range.check(SemanticVersion.FromString('2.1.1'))
    assert ver_range.check(SemanticVersion.FromString('2.0.1'))
    assert ver_range.check(SemanticVersion.FromString('2.0.0-alpha2'))
    assert ver_range.check(SemanticVersion.FromString('2.0.0-beta1'))
    assert not ver_range.check(SemanticVersion.FromString('2.0.0-alpha1'))
    assert not ver_range.check(SemanticVersion.FromString('2.0.1-alpha1'))
    assert not ver_range.check(SemanticVersion.FromString('1.1.0'))
    assert not ver_range.check(SemanticVersion.FromString('0.1.1-alpha2'))
    assert not ver_range.check(SemanticVersion.FromString('1.0.0'))


def test_filtering():
    """Make sure we can filter a range of versions against a spec."""

    ver_range = SemanticVersionRange.FromString('^2.0.0-alpha2')


    in1 = SemanticVersion.FromString('2.0.0')
    in2 = SemanticVersion.FromString('2.1.1')

    out1 = SemanticVersion.FromString('2.0.0-alpha1')

    inlist = [in1, in2, out1]

    outlist = ver_range.filter(inlist)
    outset = set(outlist)

    assert len(outset) == 2

    assert in1 in outset
    assert in2 in outset
    assert out1 not in outset


def test_filtering_keys():
    """Make sure we can filter using a key."""

    ver_range = SemanticVersionRange.FromString('^2.0.0-alpha2')


    in1 = (SemanticVersion.FromString('2.0.0'), 'a')
    in2 = (SemanticVersion.FromString('2.1.1'), 'b')

    out1 = (SemanticVersion.FromString('2.0.0-alpha1'), 'c')

    inlist = [in1, in2, out1]

    outlist = ver_range.filter(inlist, key=lambda x: x[0])
    outset = set(outlist)

    assert len(outset) == 2

    assert in1 in outset
    assert in2 in outset
    assert out1 not in outset
