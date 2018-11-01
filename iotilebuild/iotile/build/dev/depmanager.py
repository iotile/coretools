import os
from future.utils import viewitems
from typedargs import context, annotated, param, return_type, iprint, docannotate
from iotile.core.dev.iotileobj import IOTile
from iotile.core.dev.registry import ComponentRegistry
from iotile.core.exceptions import ArgumentError, ExternalError, BuildError
from .resolverchain import DependencyResolverChain


@context("DependencyManager")
class DependencyManager (object):
    """Tools to manage IOTile dependencies and build infrastructure.

    """

    def __init__(self):
        pass

    @param("path", "path", "exists", desc="Path to IOTile to check")
    @return_type('basic_dict')
    def info(self, path="."):
        """Get information on an IOTile component.

        If path is not given, the current directory is assumed to be an IOTile component.
        """

        tile = IOTile(path)

        info = {
            'is_development_version': not tile.release,
            'dependencies': tile.dependencies
        }

        return info

    @docannotate
    def list_local(self, path='.'):
        """List the absolute path of all local dependencies of this tile.

        A local dependency is defined as one that is located in the local
        ComponentRegistry().  The primary utility of this function is to
        figure out which dependencies could productively be built locally
        before building this component, vs which of its dependencies are
        pulled down from released code that is immutable.

        Args:
            path (str): The path to the iotile component that we wish to
                check local dependencies on.  If not specified, this
                defaults to the current working directory.

        Returns:
            list(str): A list of paths to each locally installed dependency.
        """

        tile = IOTile(path)

        if tile.release:
            raise ArgumentError("Cannot check dependencies on a release mode tile that cannot have dependencies")

        dep_paths = []
        reg = ComponentRegistry()

        for dep in tile.dependencies:
            try:
                local_tile = reg.find_component(dep['name'])
                if local_tile.release:
                    continue

                dep_paths.append(os.path.abspath(local_tile.folder))
            except ArgumentError:
                continue

        return dep_paths

    @return_type('map(string, string)')
    @param("path", "path", "exists", desc="Path to IOTile to check")
    def list(self, path='.'):
        """Check if all necessary dependencies of this tile are satisfied

        Returns
        =======

        A map with a string value for each dependency where the value is one of:
        - 'not installed' when there is no dependency currently in build/deps
        - 'installed' when the dependency in build/deps is valid
        - 'invalid version' when the dependency in build/deps has an invalid version
        """

        tile = IOTile(path)

        if tile.release:
            raise ArgumentError("Cannot check dependencies on a release mode tile that cannot have dependencies")

        dep_stati = {}

        for dep in tile.dependencies:
            try:
                deptile = IOTile(os.path.join(path, 'build', 'deps', dep['unique_id']))
            except (ExternalError, IOError):
                dep_stati[dep['name']] = 'not installed'
                continue

            dep_stati[dep['name']] = 'installed'

            #TODO: Check if the dependencies have the correct version

        return dep_stati

    @return_type('map(string, string)')
    @param("path", "path", "exists", desc="Path to IOTile to check")
    def versions(self, path='.'):
        """Return the version of all installed dependencies

        Returns
        =======

        A map with a string value for each dependency where the value is one of:
        - 'not installed' when there is no dependency currently in build/deps
        - 'X.Y.Z' with the version of the dependency when it is installed
        """

        tile = IOTile(path)

        if tile.release:
            raise ArgumentError("Cannot check dependencies on a release mode tile that cannot have dependencies")

        dep_stati = {}

        for dep in tile.dependencies:
            try:
                deptile = IOTile(os.path.join(path, 'build', 'deps', dep['unique_id']))
            except ExternalError as IOError:
                dep_stati[dep['name']] = 'not installed'
                continue

            dep_stati[dep['name']] = str(deptile.version)

            #TODO: Check if the dependencies have the correct version

        return dep_stati

    @param("path", "path", "exists", desc="Path to IOTile to check")
    def update_local(self, path='.'):
        """Attempt to resolve all LOCAL dependencies in this IOTile by installing them into build/deps
        """

        tile = IOTile(path)
        if tile.release:
            raise ArgumentError("Cannot update dependencies on a release mode tile that cannot have dependencies")

        depdir = os.path.join(tile.folder, 'build', 'deps')

        #FIXME: Read resolver_settings.json file
        resolver_chain = DependencyResolverChain()
        reg = ComponentRegistry()

        for dep in tile.dependencies:

            # Check each dependency to see if it's local
            try:
                local_tile = reg.find_component(dep['name'])
                if local_tile.release:
                    continue
                if local_tile is not None:
                    result = resolver_chain.update_dependency(tile, dep)

            except ArgumentError:
                continue

            iprint("Resolving %s: %s" % (dep['name'], result))

    @param("path", "path", "exists", desc="Path to IOTile to check")
    def update(self, path='.'):
        """Attempt to resolve all dependencies in this IOTile by installing them into build/deps
        """

        tile = IOTile(path)
        if tile.release:
            raise ArgumentError("Cannot update dependencies on a release mode tile that cannot have dependencies")

        depdir = os.path.join(tile.folder, 'build', 'deps')

        #FIXME: Read resolver_settings.json file
        resolver_chain = DependencyResolverChain()

        for dep in tile.dependencies:
            result = resolver_chain.update_dependency(tile, dep)
            iprint("Resolving %s: %s" % (dep['name'], result))

    @param("path", "path", "exists", desc="Path to IOTile to check")
    def clean(self, path='.'):
        """Remove all dependencies of this IOTile from build/deps
        """

        tile = IOTile(path)
        if tile.release:
            raise ArgumentError("Cannot update dependencies on a release mode tile that cannot have dependencies")

        depdir = os.path.join(tile.folder, 'build', 'deps')

        import shutil
        shutil.rmtree(depdir)
        os.makedirs(depdir)

    @param("path", "path", "exists", desc="Path to IOTile to check")
    def ensure_compatible(self, path='.'):
        """Check that all of the version of dependency tiles are compatible

        Compatible is defined as not differing by a major version number for the
        same tile.

        Raises:
            BuildError: If there are two installed dependencies that are not compatible
            ArgumentError: If not all of the tile's dependencies are installed.
        """

        orig_tile = IOTile(path)
        seen_versions = {}

        for dep in orig_tile.dependencies:
            try:
                tile = IOTile(os.path.join(path, 'build', 'deps', dep['unique_id']))

                #Check for version conflict between a directly included dependency and a dep used to build
                #a dependency.
                if tile.unique_id in seen_versions and seen_versions[tile.unique_id][0].coexistence_class != tile.parsed_version.coexistence_class:
                    raise BuildError("Version conflict between direct dependency and component used to build one of our dependencies",
                                     direct_dependency=tile.short_name, direct_version=str(tile.parsed_version),
                                     included_version=seen_versions[tile.unique_id][0],
                                     included_source=seen_versions[tile.unique_id][1])
                elif tile.unique_id not in seen_versions:
                    seen_versions[tile.unique_id] = (tile.parsed_version, 'direct')

                #Check for version conflicts between two included dependencies
                for inc_dep, inc_ver in viewitems(tile.dependency_versions):
                    if inc_dep in seen_versions and seen_versions[inc_dep][0].coexistence_class != inc_ver.coexistence_class:
                        raise BuildError("Version conflict between component used to build two of our dependencies",
                                     component_id=inc_dep,
                                     dependency_one=tile.unique_id, version_one=str(inc_ver),
                                     dependency_two=seen_versions[inc_dep][1],
                                     version_two=seen_versions[inc_dep][0])
                    elif inc_dep not in seen_versions:
                        seen_versions[inc_dep] = (inc_ver, tile.unique_id)
            except (ArgumentError, ExternalError):
                raise ArgumentError("Not all dependencies are satisfied for tile", uninstalled_dep=dep['unique_id'])
