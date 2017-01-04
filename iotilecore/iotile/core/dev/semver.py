"""Classes for parsing and dealing with semantic versions and ranges of versions
"""

from functools import total_ordering
from iotile.core.exceptions import DataError

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

    def _ordering_tuple(self):
        return (self.major, self.minor, self.patch, self.prerelease_order[self.release_type], self.prerelease_number)

    def __str__(self):
        version = "{0}.{1}.{2}".format(self.major, self.minor, self.patch)

        if self.release_type is not 'release':
            version += '-{0}{1}'.format(self.release_type, self.prerelease_number)

        return version

    def __eq__(self, other):
        return self._ordering_tuple() == other._ordering_tuple()

    def __lt__(self, other):
        return self._ordering_tuple() < other._ordering_tuple()

    def __hash__(self):
        return hash(self._ordering_tuple())
