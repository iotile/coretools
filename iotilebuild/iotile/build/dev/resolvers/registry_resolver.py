import os
from .depresolver import DependencyResolver
from iotile.core.exceptions import ArgumentError, ExternalError, IOTileException
from iotile.core.utilities.typedargs import iprint
from iotile.core.dev.iotileobj import IOTile

class ComponentRegistryResolver (DependencyResolver):
    """Attempt to find a component's dependency in the local registry
    """
    def __init__(self, settings={}):
        pass

    def resolve(self, depinfo, destdir):
        from iotile.core.dev.registry import ComponentRegistry

        reg = ComponentRegistry()

        try:
            comp = reg.find_component(depinfo['name'])
        except ArgumentError:
            return {'found': False}

        # Make sure the tile we found in the registry has the required version
        reqver = depinfo['required_version']
        if not reqver.check(comp.parsed_version):
            return {'found': False}

        # If the component is in the local registry but hasn't been built,
        # raise an error.

        if not os.path.exists(comp.output_folder):
            raise ExternalError("Component found in registry but has not been built", path=comp.folder, name=comp.name, suggestion="Run iotile build on this component first")

        try:
            IOTile(comp.output_folder)
        except IOTileException:
            raise ExternalError("Component found in registry but its build/output folder is not valid", path=comp.folder, name=comp.name, suggestion="Cleanly rebuild the component")

        self._copy_folder_contents(comp.output_folder, destdir)
        return {'found': True}

    def check(self, depinfo, deptile, depsettings):
        from iotile.core.dev.registry import ComponentRegistry

        reg = ComponentRegistry()

        try:
            comp = reg.find_component(depinfo['name'])
        except ArgumentError:
            return True

        #If the component does not have a matching version, we cannot assess up-to-date-ness
        #FIXME: We should return that we cannot assess up to dateness, not that we are up to date
        reqver = depinfo['required_version']
        if not reqver.check(comp.parsed_version):
            return True

        #If the component in the registry has a higher version or a newer release date, it should
        #be updated
        if comp.parsed_version > deptile.parsed_version:
            return False

        if comp.release_date is not None and comp.release_date > deptile.release_date:
            return False

        return True
