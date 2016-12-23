from iotile.core.exceptions import *
from iotile.core.dev.iotileobj import IOTile
import os
import json
import resolvers
import re
import pkg_resources
import logging

class DependencyResolverChain(object):
    """A set of rules mapping dependencies to DependencyResolver instances

    DependencyResolverChains let you customize which dependencies are looked up
    in which way.  For example, you could have some dependencies resolved using
    github while others must be installed locally.

    The default DependencyResolverChain requires that all dependencies be installed
    locally and registered with the IOTile Registry.
    """

    def __init__(self, settings_file=None):
        self.rules = []

        logger = logging.getLogger('iotile.build.warnings')
        logger.addHandler(logging.NullHandler)

        #FIXME: Load settings_file

        #Find all registered default builders and load them in priority order
        #Each default resolver should be a 4-tuple with (priority, matching_regex, factory, default args)
        for entry in pkg_resources.iter_entry_points('iotile.build.default_depresolver'):
            resolver_entry = entry.load()
            try:
                priority, regex, factory, settings = resolver_entry
            except TypeError:
                logger.warn('Invalid default resolver entry that was not a 4-tuple: %s', str(resolver_entry))
                continue

            self.rules.append((priority, (regex, factory, settings)))

        self.rules.sort(key=lambda x: x[0])

    def update_dependency(self, tile, depinfo):
        """Attempt to install or update a dependency to the latest version.

        Args:
            tile (IOTile): An IOTile object describing the tile that has the dependency
            depinfo (dict): a dictionary from tile.dependencies specifying the dependency

        Returns:
            string: a string indicating the outcome.  Possible values are:
                "already installed"
                "installed"
                "updated"
                "not found"
        """

        destdir = os.path.join(tile.folder, 'build', 'deps', depinfo['unique_id'])
        has_version = False
        if os.path.exists(destdir):
            has_version = True

        for priority, rule in self.rules:
            if not self._check_rule(rule, depinfo):
                continue

            resolver = self._find_resolver(rule)

            if has_version:
                deptile = IOTile(destdir)

                #If the dependency is up to date, don't do anything
                if self._check_dep(depinfo, deptile, resolver):
                    continue

                #Otherwise remove the current dependency and reload it
                import shutil
                shutil.rmtree(destdir)

            #Now try to resolve this dependency with the latest version
            result = resolver.resolve(depinfo, destdir)
            if not result['found'] and result.get('stop', False):
                return 'not found'

            if not result['found']:
                continue

            settings = {
                'resolver': resolver.__class__.__name__
            }
            if 'settings' in result:
                settings['settings'] = result['settings']

            self._save_depsettings(destdir, settings)

            if has_version:
                return "updated"
            else:
                return "installed"

        if has_version:
            return "already installed"

        return "not found"


    def _save_depsettings(self, destdir, settings):
        settings_file = os.path.join(destdir, 'dep_settings.json')

        with open(settings_file, 'wb') as f:
            json.dump(settings, f, indent=4)

    def _load_depsettings(self, deptile):
        settings_file = os.path.join(deptile.folder, 'dep_settings.json')

        with open(settings_file, 'rb') as f:
            settings = json.load(f)

        return settings

    def _check_dep(self, depinfo, deptile, resolver):
        """Check if a dependency tile is up to date
        """

        try:
            settings = self._load_depsettings(deptile)
        except IOError as e:
            return False

        #If this dependency was initially resolved with a different resolver, then 
        #we cannot check if it is up to date
        if settings['resolver'] != resolver.__class__.__name__:
            return False

        resolver_settings = {}
        if 'settings' in settings:
            resolver_settings = settings['settings']

        return resolver.check(depinfo, deptile, resolver_settings)
    
    def _find_resolver(self, rule):
        regex,factory,args = rule
        return factory(args)

    def _check_rule(self, rule, depinfo):
        regex,factory,args = rule

        if regex.match(depinfo['name']):
            return True

        return False