import pkg_resources
import os.path
import SCons

#See if any installed package is advertising scons builders
for entry in pkg_resources.iter_entry_points('iotile.builder'):
    path_gen = entry.load()
    tool_path = path_gen()

    SCons.Tool.DefaultToolpath.insert(0, os.path.abspath(tool_path))

SCons.Defaults.DefaultEnvironment(tools=[])
