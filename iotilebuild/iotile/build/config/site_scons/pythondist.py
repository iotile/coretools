import utilities
import unit_test
from SCons.Script import *
import os.path
import os
import sys
import itertools
import arm
import platform
from docbuild import *
from release import *
from iotile.core.exceptions import *
import iotile.core
from dependencies import find_dependency_wheels, _iter_dependencies
from iotile.build.utilities.template import RecursiveTemplate
from iotile.core.dev.iotileobj import IOTile
import pkg_resources
import setuptools.sandbox

def build_python_distribution(tile):
    env = Environment(tools=[])
    srcdir = 'python'
    builddir = os.path.join('build', 'python')
    outdir = os.path.join('build', 'output', 'python')
    outsrcdir = os.path.join(outdir, 'src')

    proxies = tile.proxy_modules()
    typelibs = tile.type_packages()
    plugins = tile.proxy_plugins()

    if len(proxies) == 0 and len(typelibs) == 0 and len(plugins) == 0:
        return

    srcfiles = [os.path.basename(x) for x in itertools.chain(iter(proxies), iter(typelibs), iter(plugins))]
    buildfiles = []
    
    for infile in srcfiles:
        inpath = os.path.join(srcdir, infile)
        outfile = os.path.join(outsrcdir, infile)
        buildfile = os.path.join(builddir, infile)

        env.Command(outfile, inpath, Copy("$TARGET", "$SOURCE"))
        env.Command(buildfile, inpath, Copy("$TARGET", "$SOURCE"))
        buildfiles.append(buildfile)

    #Create setup.py file and then use that to build a python wheel 
    env['TILE'] = tile
    wheel_output = os.path.join('build', 'python', 'dist', tile.support_wheel)

    env.Command([os.path.join(builddir, 'setup.py'), wheel_output], ['module_settings.json'] + buildfiles, action=Action(generate_setup_py, "Building python distribution"))
    env.Command([os.path.join(outdir, tile.support_wheel)], [wheel_output], Copy("$TARGET", "$SOURCE"))

    #Also copy over all dependency wheels as well
    wheels = find_dependency_wheels(tile)

    for wheel in wheels:
        wheel_name = os.path.basename(wheel)
        env.Command([os.path.join(outdir, wheel_name)], [wheel], Copy("$TARGET", "$SOURCE"))

def generate_setup_py(target, source, env):
    tile = env['TILE']
    data = {}

    #Figure out the packages and modules that we need to put in this package
    typelibs = [os.path.basename(x) for x in tile.type_packages()]
    mods = [os.path.splitext(os.path.basename(x))[0] for x in itertools.chain(iter(tile.proxy_modules()), iter(tile.proxy_plugins()))]

    #Now figure out all of the entry points that group type_packages, proxy_plugins and proxy_modules 
    #and allow us to find them.

    entry_points = {}

    modentries = [os.path.splitext(os.path.basename(x))[0] for x in tile.proxy_modules()]
    pluginentries = [os.path.splitext(os.path.basename(x))[0] for x in tile.proxy_plugins()]
    
    if len(modentries) > 0:
        entry_points['iotile.proxy'] = ["{0} = {0}".format(x) for x in modentries]
    if len(pluginentries) > 0:
        entry_points['iotile.proxy_plugin'] = ["{0} = {0}".format(x) for x in pluginentries]
    if len(typelibs) > 0:
        entry_points['iotile.type_package'] = ["{0} = {0}".format(x) for x in typelibs]

    data['name'] = tile.support_distribution
    data['packages'] = typelibs
    data['modules'] = mods
    data['version'] = tile.version
    data['deps'] = ["{0} ~= {1}.{2}".format(x.support_distribution, x.parsed_version.major, x.parsed_version.minor) for x in _iter_dependencies(tile) if x.has_wheel]
    data['entry_points'] = entry_points

    outdir = os.path.dirname(str(target[0]))
    setup_template = RecursiveTemplate('setup.py', pkg_resources.resource_filename(pkg_resources.Requirement.parse("iotile-build"), "iotile/build/config/templates"))

    setup_template.add(data)
    setup_template.render(outdir)

    #Run setuptools to generate a wheel
    curr = os.getcwd()
    os.chdir(outdir)
    try:
        setuptools.sandbox.run_setup('setup.py', ['-q', 'clean', 'bdist_wheel'])
    finally:
        os.chdir(curr)

    wheel_output = os.path.join(outdir, 'dist', tile.support_wheel)
