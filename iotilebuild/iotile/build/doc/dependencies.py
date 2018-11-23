from docutils.parsers.rst import Directive
import docutils
import os.path
from iotile.core.dev.registry import ComponentRegistry
import json
import sphinx
from docutils.statemachine import ViewList
from iotile.core.exceptions import ArgumentError

#TODO: Modify this to not list whether the dependency is installed or not

class DependenciesDirective (Directive):
    """Directive for adding a list of all dependencies used by this component

    This directive parses the module_settings.json file for the component and
    adds links to any installed dependencies that it finds there.
    """

    def run(self):
        component = os.path.abspath('.')
        deps = self._get_dependencies(component)
        reg = ComponentRegistry()

        found = []
        not_found = []

        for name in deps:
            try:
                tile = reg.find_component(name)
                found.append(tile)
            except ArgumentError:
                not_found.append(name)

        deplines = []

        for tile in found:
            deplines.append('- %s' % tile.name)

        for name in not_found:
            deplines.append('- %s (NOT INSTALLED)' % name)

        view = ViewList(deplines, 'dependencies-directive')

        node = docutils.nodes.paragraph()
        sphinx.util.nodes.nested_parse_with_titles(self.state, view, node)
        return node.children

    def _get_dependencies(self, component):
        module_settings = os.path.join(component, 'module_settings.json')

        with open(module_settings, "r") as f:
            settings = json.load(f)

        mod = list(settings['modules'])[0]
        mod_settings = settings['modules'][mod]

        if 'depends' not in mod_settings:
            return {}

        return mod_settings['depends']
