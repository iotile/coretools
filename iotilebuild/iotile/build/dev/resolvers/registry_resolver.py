from depresolver import DependencyResolver
from iotile.core.exceptions import ArgumentError

class ComponentRegistryResolver (DependencyResolver):
    def __init__(self, settings={}):
        pass

    def resolve(self, depinfo, destdir):
        from iotile.core.dev.registry import ComponentRegistry

        reg = ComponentRegistry()

        try:
            comp = reg.find_component(depinfo['name'])
        except ArgumentError:
            return {'found': False}

        self._copy_folder_contents(comp.output_folder, destdir)
        return {'found': True}

    def check(self, depinfo, deptile, depsettings):
        from iotile.core.dev.registry import ComponentRegistry

        reg = ComponentRegistry()

        try:
            comp = reg.find_component(depinfo['name'])
        except ArgumentError:
            return True

        if comp.release_date is not None and comp.release_date > deptile.release_date:
            return False

        return True

