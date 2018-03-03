"""Classes for parsing and dealing with semantic versions and ranges of versions
"""

from functools import total_ordering
from iotile.core.exceptions import DataError, ArgumentError

@total_ordering
class SemanticVersion(object):
    """A simple class representing a version in X.Y.Z[-prerelease] format

    Only a known number of prerelease types are allowed and must be in the format:
    <name><integer>

    where name is one of: build, alpha, beta, rc
    and integer is a whole number greater than 0

    The sort order for prereleases is defined as build < alpha < beta < rc < release
    """

    prerelease_order = {'build': 0, 'alpha': 1, 'beta': 2, 'rc': 3, 'release': 4}

    def __init__(self, major, minor, patch, release_type='release', prerelease_number=None):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.release_type = release_type
        self.prerelease_number = prerelease_number

    def inc_first_nonzero(self):
        """Create a new SemanticVersion with the first nonzero value incremented

        If this version is 0.0.1, then this will return 0.0.2.  If this version
        if 0.1.0 then this version will return 0.2.0.

        All prerelease information is stripped so 1.0.0-alpha2 becomes 2.0.0.
        """

        release = [x for x in self.release_tuple]

        if release[0] == 0 and release[1] == 0:
            release[2] += 1
        elif release[0] == 0:
            release[1] += 1
            release[2] = 0
        else:
            release[0] += 1
            release[1] = 0
            release[2] = 0

        return SemanticVersion(*release)

    @property
    def coexistence_class(self):
        """A tuple representing the compatibility class of this semantic version

        Coexistence classes are defined as a tuple containing the release version
        with everything except the first nonzero entry being zero.  Basically,
        coexistence classes divide version into those that should be compatible
        based on semantic versioning rules
        """

        out = self.release_tuple

        if out[0] == 0 and out[1] == 0:
            return out
        elif out[0] == 0:
            return (out[0], out[1], 0)
        else:
            return (out[0], 0, 0)

    def inc_release(self):
        """Create a new SemanticVersion with the patch level incremented

        All prerelease information is stripped.  So 0.0.1-alpha2 becomes 0.0.2
        """

        release = [x for x in self.release_tuple]
        release[2] += 1

        return SemanticVersion(*release)

    @property
    def is_release(self):
        return self.release_type == 'release'

    @property
    def is_prerelease(self):
        return not self.is_release

    @classmethod
    def ParsePrerelease(cls, prerelease):
        """Parse a prerelease string into a type, number tuple

        Args:
            prerelease (string): a prerelease string in the format specified for SemanticVersion

        Returns:
            tuple: (release_type, number)
        """

        last_alpha = 0
        while last_alpha < len(prerelease) and prerelease[last_alpha].isalpha():
            last_alpha += 1

        release_type = prerelease[:last_alpha]
        release_number = prerelease[last_alpha:]

        if release_type not in SemanticVersion.prerelease_order or release_type == 'release':
            raise DataError("Invalid Prerelease specifier in semantic version", prerelease_type=release_type)

        try:
            release_number = int(release_number)
        except ValueError:
            raise DataError("Invalid Prerelease number in semantic version", prerelease_number=release_number)

        return (release_type, release_number)

    @classmethod
    def FromString(cls, version):
        parts = version.split('.')
        if len(parts) != 3:
            raise DataError("Invalid version format in SemanticVersion, must be X.Y.Z[-prerelease]", version=version)

        major = int(parts[0])
        minor = int(parts[1])

        if '-' in parts[2]:
            patchstr, prerelease = parts[2].split('-')
            patch = int(patchstr)

            release_type, prerelease_num = cls.ParsePrerelease(prerelease)
        else:
            patch = int(parts[2])
            release_type = 'release'
            prerelease_num = None

        return SemanticVersion(major, minor, patch, release_type, prerelease_num)

    @property
    def release_tuple(self):
        """Return the X.Y.Z prefix for this version
        """

        return (self.major, self.minor, self.patch)

    def _ordering_tuple(self):
        return (self.major, self.minor, self.patch, self.prerelease_order[self.release_type], self.prerelease_number)

    def __str__(self):
        version = "{0}.{1}.{2}".format(self.major, self.minor, self.patch)

        if self.release_type is not 'release':
            version += '-{0}{1}'.format(self.release_type, self.prerelease_number)

        return version

    def pep440_string(self):
        """Convert this version into a python PEP 440 compliant string.

        There is a 1:1 map between versions as specified in these SemanticVersion
        objects and what is allowed in python packages according to PEP 440.  This
        function does that conversion and returns a pep440 compliant string.

        Released versions are identical to what is returned by str(self), however,
        preleases have the following mapping (assuming X.Y.Z is the public release):

        X.Y.Z:
            X.Y.Z

        X.Y.Z-alphaN:
            X.Y.ZaN

        X.Y.Z-betaN:
            X.Y.ZbN

        X.Y.Z-rcN:
            X.Y.ZrcN

        X.Y.Z-buildN:
            X.Y.Z.devN

        Returns:
            str: The PEP 440 compliant version string.
        """

        if self.is_release:
            return str(self)

        prerelease_templates = {
            "build": "%d.%d.%d.dev%d",
            "alpha": "%d.%d.%da%d",
            "beta": "%d.%d.%db%d",
            "rc": "%d.%d.%drc%d"
        }

        template = prerelease_templates[self.release_type]
        return template % (self.major, self.minor, self.patch, self.prerelease_number)

    def __eq__(self, other):
        return self._ordering_tuple() == other._ordering_tuple()

    def __lt__(self, other):
        return self._ordering_tuple() < other._ordering_tuple()

    def __hash__(self):
        return hash(self._ordering_tuple())


class SemanticVersionRange(object):
    """Class specifying a range of SemanticVersion objects

    Ranges can be used to filter a list of SemanticVersion objects into
    only those that satisfy the range conditions.  Currently, only a minimal
    set of range operations is supported.  Range parsing and interpretation
    is taken from npm semver:

    https://docs.npmjs.com/misc/semver

    Currently, the only operations that are implemented in the parser is:

    ^X.Y.Z

    The preferred way to create a SemanticVersionRange is through the classmethod
    FromString("<version range spec>").

    Args:
        disjuncts (list): A list of lists of 4 tuples that specify the ranges to be matched
            Each tuple should (lower, upper, inclusive_lower, inclusive_upper) where
            lower and upper and SemanticVersions (possibly None) and inclusive_* are
            bools that determine whether the range condition is <= upper or < upper
            (>= lower, > lower).  Each sublist is joined conjunctively within itself
            and the lists themselves are joined disjunctively.
    """

    def __init__(self, disjuncts):
        self._disjuncts = disjuncts

    def _check_ver_range(self, version, ver_range):
        """Check if version is included in ver_range
        """

        lower, upper, lower_inc, upper_inc = ver_range

        #If the range extends over everything, we automatically match
        if lower is None and upper is None:
            return True

        if lower is not None:
            if lower_inc and version < lower:
                return False
            elif not lower_inc and version <= lower:
                return False

        if upper is not None:
            if upper_inc and version > upper:
                return False
            elif not upper_inc and version >= upper:
                return False

        #Prereleases have special matching requirements
        if version.is_prerelease:
            #Prereleases cannot match ranges that are not defined as prereleases
            if (lower is None or not lower.is_prerelease) and (upper is None or not upper.is_prerelease):
                return False

            #Prereleases without the same major.minor.patch as a range end point cannot match
            if (lower is not None and version.release_tuple != lower.release_tuple) and \
               (upper is not None and version.release_tuple != upper.release_tuple):
                return False

        return True

    def _check_insersection(self, version, ranges):
        """Check that a version is inside all of a list of ranges
        """

        for ver_range in ranges:
            if not self._check_ver_range(version, ver_range):
                return False

        return True

    def check(self, version):
        """Check that a version is inside this SemanticVersionRange

        Args:
            version (SemanticVersion): The version to check

        Returns:
            bool: True if the version is included in the range, False if not
        """

        for disjunct in self._disjuncts:
            if self._check_insersection(version, disjunct):
                return True

        return False

    def filter(self, versions, key=lambda x: x):
        """Filter all of the versions in an interable that match this version range

        Args:
            versions (iterable): An iterable of SemanticVersion objects

        Returns:
            list: A list of the SemanticVersion objects that matched this range
        """

        return [x for x in versions if self.check(key(x))]

    @classmethod
    def FromString(cls, range_string):
        """Parse a version range string into a SemanticVersionRange

        Currently, the only possible range strings are:

        ^X.Y.Z - matches all versions with the same leading nonzero digit
            greater than or equal the given range.
        * - matches everything
        =X.Y.Z - matches only the exact version given

        Args:
            range_string (string): A string specifying the version range

        Returns:
            SemanticVersionRange: The resulting version range object

        Raises:
            ArgumentError: if the range string does not define a valid range.
        """

        disjuncts = None

        range_string = range_string.strip()

        if len(range_string) == 0:
            raise ArgumentError("You must pass a finite string to SemanticVersionRange.FromString", range_string=range_string)

        #Check for *
        if len(range_string) == 1 and range_string[0] == '*':
            conj = (None, None, True, True)
            disjuncts = [[conj]]

        #Check for ^X.Y.Z
        elif range_string[0] == '^':
            ver = range_string[1:]

            try:
                ver = SemanticVersion.FromString(ver)
            except DataError as err:
                raise ArgumentError("Could not parse ^X.Y.Z version", parse_error=str(err), range_string=range_string)

            lower = ver
            upper = ver.inc_first_nonzero()

            conj = (lower, upper, True, False)
            disjuncts = [[conj]]
        elif range_string[0] == '=':
            ver = range_string[1:]

            try:
                ver = SemanticVersion.FromString(ver)
            except DataError as err:
                raise ArgumentError("Could not parse =X.Y.Z version", parse_error=str(err), range_string=range_string)

            conj = (ver, ver, True, True)
            disjuncts = [[conj]]

        if disjuncts is None:
            raise ArgumentError("Invalid range specification that could not be parsed", range_string=range_string)

        return SemanticVersionRange(disjuncts)
