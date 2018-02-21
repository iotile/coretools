import os
from iotile.core.exceptions import BuildError
from .provider import ReleaseProvider


class PyPIReleaseProvider(ReleaseProvider):
    """Release a component's python support package to a Pypi repository.

    This release provider will upload the python support wheel and sdist
    associated with this component to PyPI or another python package
    repository.  You must have associated credentials for the package
    reposity set in the following environment variables:

    PYPI_USER: username
    PYPI_PASS: password

    Args:
        args (dict): Whatever arguments were specified for this release provider in module_settings.json
            You can specify only one argument:
            - repository (str): The repository that we should upload the package to.  If this is not
              specified then it defaults to PYPI ()
        component (IOTile): The IOTile object that should be released.  It must be a release mode IOTile
            object.
    """

    def __init__(self, component, args):
        super(PyPIReleaseProvider, self).__init__(component, args)

        self.repo = args.get('repository', 'pypi')
        self.dists = []

    def stage(self):
        """Stage python packages for release, verifying everything we can about them."""

        if 'PYPI_USER' not in os.environ or 'PYPI_PASS' not in os.environ:
            raise BuildError("You must set the PYPI_USER and PYPI_PASS environment variables")

        try:
            import twine
        except ImportError:
            raise BuildError("You must install twine in order to release python packages", suggestion="pip install twine")

        if not self.component.has_wheel:
            raise BuildError("You cannot release a component to a PYPI repository if it doesn't have any python packages")

        # Make sure we have built distributions ready to upload
        wheel = self.component.support_wheel
        sdist = "%s-%s.tar.gz" % (self.component.support_distribution, self.component.parsed_version.pep440_string())

        wheel_path = os.path.realpath(os.path.abspath(os.path.join(self.component.output_folder, 'python', wheel)))
        sdist_path = os.path.realpath(os.path.abspath(os.path.join(self.component.output_folder, 'python', sdist)))

        if not os.path.isfile(wheel_path) or not os.path.isfile(sdist_path):
            raise BuildError("Could not find built wheel or sdist matching current built version", sdist_path=sdist_path, wheel_path=wheel_path)

        self.dists = [sdist_path, wheel_path]

    def unstage(self):
        """Cleanup anything we did during staging."""
        pass

    def release(self):
        """Release this component to a pypi repository."""

        self._upload_dists(self.repo, self.dists)

    def unrelease(self):
        """Unrelease this component from a pypi repository."""
        raise BuildError("Cannot unrelease a released python package")

    def _upload_dists(self, repo, dists):
        """Upload a given component to pypi

        The pypi username and password must either be specified in a ~/.pypirc
        file or in environment variables PYPI_USER and PYPI_PASS
        """

        from twine.commands.upload import upload

        if 'PYPI_USER' in os.environ and 'PYPI_PASS' in os.environ:
            pypi_user = os.environ['PYPI_USER']
            pypi_pass = os.environ['PYPI_PASS']
        else:
            pypi_user = None
            pypi_pass = None

        #Invoke upload this way since subprocess call of twine cli has cross platform issues
        upload(dists, repo, False, None, pypi_user, pypi_pass, None, None, '~/.pypirc', False, None, None, None)
