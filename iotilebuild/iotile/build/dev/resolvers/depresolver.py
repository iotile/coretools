from iotile.core.exceptions import NotFoundError

class DependencyResolver (object):
    """An object that is capable of finding and installing a dependency
    """

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

        raise NotFoundError("DependencyResolver did not implement resolve method")

    def check(self, depinfo, deptile, depsettings):
        """Check if this dependency is the latest version in a subclass defined way


        Args:
            depinfo (dict): a dictionary returned by IOTile.dependencies describing the dependency
            deptile (IOTile): an IOTile object for the installed dependency
            depsettings (dict): a dictionary that was previously stored with this dependency by resolve

        Returns:
            bool: True meaning the dependency is up-to-date or False if it is not.
        """

        raise NotFoundError("DependencyResolver did not implement check method")

    def _copy_folder_contents(self, source, dest):
        
        import shutil
        shutil.copytree(source, dest)
