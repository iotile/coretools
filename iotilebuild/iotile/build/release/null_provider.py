from .provider import ReleaseProvider
from iotile.core.exceptions import BuildError

class NullReleaseProvider(ReleaseProvider):
    """A Noop release provider for testing purposes
    """

    def stage(self):
        """Stage this component for release
        """

        if self.args.get('stage_error', False):
            raise BuildError("Staging error triggered in NullReleaseProvider")

    def unstage(self):
        """Unstage this component assuming that stage succeeded
        """

        if self.args.get('unstage_error', False):
            raise BuildError("Unstaging error triggered in NullReleaseProvider")

    def release(self):
        """Release this component assuming that stage succeeded
        """

        if self.args.get('release_error', False):
            raise BuildError("Release error triggered in NullReleaseProvider")

    def unrelease(self):
        """Unrelease this component assuming that release succeeded
        """

        if self.args.get('unrelease_error', False):
            raise BuildError("Staging error triggered in NullReleaseProvider")
