"""A mock DependencyResolver object for testing iotile-build"""

from iotile.core.dev.iotileobj import IOTile


class MockDependencyResolver:
    def __init__(self, args):
        self.known_deps = {IOTile(x).unique_id: IOTile(x) for x in args}

    def resolve(self, depinfo, destdir):
        """Attempt to resolve this dependency using a subclass defined method
        
        Args:
            depinfo (dict): a dictionary returned by IOTile.dependencies describing the dependency
            destdir (string): the directory that the dependency should be copied into

        Returns:
            dict: The function returns a dictionary that has required and optional keys.  The 
                required keys are:
                    found: boolean if this resolver found a matching dependency

                optional keys are:
                    stop:   boolean if this resolver is suggesting that we should stop looking for this
                            dependency. This is useful for making a resolver that stops a resolver chain
                    info:   a dictionary that contains information that this resolver wants to store
                            with the dependency for future reference.
        """

        if depinfo['unique_id'] not in self.known_deps:
            return {'found': False}

        dep = self.known_deps[depinfo['unique_id']]
        if depinfo['required_version'].check(dep.parsed_version):
            self._copy_folder_contents(dep.output_folder, destdir)
            return {'found': True}

        return {'found': False}

    def check(self, depinfo, deptile, depsettings):
        """Check if this dependency is the latest version in a subclass defined way


        Args:
            depinfo (dict): a dictionary returned by IOTile.dependencies describing the dependency
            deptile (IOTile): an IOTile object for the installed dependency
            depsettings (dict): a dictionary that was previously stored with this dependency by resolve

        Returns:
            bool: True meaning the dependency is up-to-date or False if it is not.

        Raises:
            ExternalError: if the checking process was not able to assess whether the dependency was 
                up to date or not.
        """

        if depinfo['unique_id'] not in self.known_deps:
            raise ExternalError("Could not check dependency's status", unique_id=depinfo['unique_id'])

        dep = self.known_deps[depinfo['unique_id']]
        if not depinfo['required_version'].check(dep.parsed_version):
            return True

        if deptile.parsed_version < dep.parsed_version:
            return False

        return True

    def _copy_folder_contents(self, source, dest):
        import shutil
        shutil.copytree(source, dest)
