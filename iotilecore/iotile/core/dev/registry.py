# This file is copyright Arch Systems, Inc.  
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from iotile.core.utilities.kvstore import KeyValueStore
from iotile.core.exceptions import *
import json
import os.path
from iotileobj import IOTile
import pkg_resources
import imp

class ComponentRegistry:
    """
    ComponentRegistry

    A mapping of all of the installed components on this system that can
    be used as build dependencies and where they are located.  Also used
    to manage iotile plugins.
    """

    def __init__(self):
        self.kvstore = KeyValueStore('component_registry.db', respect_venv=True)
        self.plugins = {}
        
        for entry in pkg_resources.iter_entry_points('iotile.plugin'):
                plugin = entry.load()
                links = plugin()
                for name,value in links:
                    self.plugins[name] = value

    def add_component(self, component):
        """
        Register a component with ComponentRegistry. 

        Component must be a buildable object with a module_settings.json file that
        describes its name and the domain that it is part of.
        """

        tile = IOTile(component)
        value = os.path.normpath(os.path.abspath(component))

        self.kvstore.set(tile.name, value)

    def list_plugins(self):
        """
        List all of the plugins that have been registerd for the iotile program on this computer
        """

        vals = self.plugins.items()

        return {x: y for x,y in vals}

    def find_component(self, key, domain=""):
        try:
            if domain is not "":
                key = domain.lower() + '/' + key.lower()

            return IOTile(self.kvstore.get(key))
        except KeyError:
            raise ArgumentError("Unknown component name", name=key)

    def remove_component(self, key):
        """
        Remove component from registry
        """

        return self.kvstore.remove(key)

    def clear_components(self):
        """
        Clear all of the registered components
        """

        self.kvstore.clear()

    def list_components(self):
        """
        List all of the registered component names
        """

        items = self.kvstore.get_all()

        return [x[0] for x in items]

    def check_components(self):
        """
        Check where all registered components are up-to-date git repositories
        
        Returns a map listing all of the components that are not in a clean state,
        either with uncommitted changes or with their master branch not in sync with
        origin.
        """

        comps = self.kvstore.get_all()

        from git import Repo
        import git

        stati = {}

        for name, folder in comps:
            try:
                repo = Repo(folder)
            except git.exc.InvalidGitRepositoryError:
                stati[name] = "not a git repo"
                continue

            try:
                origin = repo.remotes['origin']
            except IndexError:
                stati[name] = "does not have a remote origin configured"
                continue

            origin.fetch()

            #Check status if we're up to date with remote
            count_ahead = sum(1 for c in repo.iter_commits('master..origin/master'))
            count_behind = sum(1 for c in repo.iter_commits('origin/master..master'))

            if count_ahead > 0 or count_behind > 0:
                stati[name] = "not in sync with remote (%d ahead, %d behind"
                continue

            dirty_files = list(repo.index.diff(None))
            untracked = len(repo.untracked_files)
            if len(dirty_files) > 0 or untracked > 0:
                stati[name] = "has %d files with uncommitted changes and %d untracked files" % (len(dirty_files), untracked)

            #Otherwise don't add it to the list of dirty repositories 
        return stati
