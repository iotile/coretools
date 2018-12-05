import os.path
import os
import sys
import glob
import itertools
from SCons.Script import *
from docbuild import *
from release import *
from iotile.core.exceptions import *
from dependencies import find_dependency_wheels, _iter_dependencies
from iotile.build.utilities import render_template
from iotile.core.dev.iotileobj import IOTile
import setuptools.sandbox


def build_python_distribution(tile):
    env = Environment(tools=[])
    srcdir = 'python'
    builddir = os.path.join('build', 'python')
    packagedir = os.path.join(builddir, tile.support_distribution)
    outdir = os.path.join('build', 'output', 'python')
    outsrcdir = os.path.join(outdir, 'src')

    proxies = tile.proxy_modules()
    typelibs = tile.type_packages()
    plugins = tile.proxy_plugins()
    appmodules = tile.app_modules()
    buildentries = tile.build_steps()

    buildentry_modules = [x.split(':')[0] for x in buildentries]

    if len(proxies) == 0 and len(typelibs) == 0 and len(plugins) == 0 and len(appmodules) == 0 and len(buildentries) == 0:
        return

    srcnames = [os.path.basename(x) for x in itertools.chain(iter(proxies), iter(buildentry_modules), iter(typelibs), iter(plugins), iter(appmodules))]
    buildfiles = []

    pkg_init = os.path.join(packagedir, '__init__.py')

    # Make sure we always clean up the temporary python directory that we are creating
    # so that there are no weird build issues
    env.Command(pkg_init, [], [
        Delete(builddir),
        Mkdir(builddir),
        Mkdir(packagedir),
        Touch(pkg_init)
        ])

    # Make sure build/output/python/src exists
    # We create a timestamp placeholder file so that other people can depend
    # on this directory and we always delete it so that we reclean everything
    # up and don't have any old files.
    outsrcnode = env.Command(os.path.join(outsrcdir, ".timestamp"), [], [
        Delete(outsrcdir),
        Mkdir(outsrcdir),
        Touch(os.path.join(outsrcdir, ".timestamp"))])

    for infile in srcnames:
        inpath = os.path.join(srcdir, infile)
        outfile = os.path.join(outsrcdir, infile)
        buildfile = os.path.join(packagedir, infile)

        if os.path.isdir(inpath):
            srclist = inpath
        else:
            srclist = [inpath]

        target = env.Command(outfile, srclist, Copy("$TARGET", "$SOURCE"))
        env.Depends(target, outsrcnode)

        env.Command(buildfile, [inpath, pkg_init], Copy("$TARGET", "$SOURCE"))

        buildfiles.append(buildfile)

    #Create setup.py file and then use that to build a python wheel and an sdist
    env['TILE'] = tile
    support_sdist = "%s-%s.tar.gz" % (tile.support_distribution, tile.parsed_version.pep440_string())
    wheel_output = os.path.join('build', 'python', 'dist', tile.support_wheel)
    sdist_output = os.path.join('build', 'python', 'dist', support_sdist)

    env.Clean(os.path.join(outdir, tile.support_wheel), os.path.join('build', 'python'))
    env.Command([os.path.join(builddir, 'setup.py'), wheel_output], ['module_settings.json'] + buildfiles,
                action=Action(generate_setup_py, "Building python distribution"))

    env.Depends(sdist_output, wheel_output)
    env.Command([os.path.join(outdir, tile.support_wheel)], [wheel_output], Copy("$TARGET", "$SOURCE"))
    env.Command([os.path.join(outdir, support_sdist)], [sdist_output], Copy("$TARGET", "$SOURCE"))

    #Also copy over all dependency wheels as well
    wheels = find_dependency_wheels(tile)

    if "python_universal" in tile.settings:
        required_version = "py2.py3"
    else:
        required_version = "py3" if sys.version_info[0] == 3 else "py2"

    for wheel in wheels:

        wheel_name = os.path.basename(wheel)
        wheel_basename = '-'.join(wheel.split('-')[:-3])
        wheel_pattern = wheel_basename + "-*" + required_version + '*'

        wheel_source = glob.glob(wheel_pattern)
        wheel_real = glob.glob(wheel_basename + '*')

        if wheel_source:
            env.Command([os.path.join(outdir, wheel_name)], [wheel_source[0]], Copy("$TARGET", "$SOURCE"))
        else:
            print("This package is set up to require", required_version)
            print("Dependency version appears to be", wheel_real[0].split('/')[-1])
            raise BuildError("dependent wheel not built with compatible python version")


def generate_setup_py(target, source, env):
    """Generate the setup.py file for this distribution."""

    tile = env['TILE']
    data = {}

    # Figure out the packages and modules that we need to put in this package
    typelibs = [os.path.basename(x) for x in tile.type_packages()]

    # Now figure out all of the entry points that group type_packages, proxy_plugins and proxy_modules
    # and allow us to find them.

    entry_points = {}

    modentries = [os.path.splitext(os.path.basename(x))[0] for x in tile.proxy_modules()]
    pluginentries = [os.path.splitext(os.path.basename(x))[0] for x in tile.proxy_plugins()]
    appentries = [os.path.splitext(os.path.basename(x))[0] for x in tile.app_modules()]

    buildentries = tile.build_steps()
    buildentry_parsed = [x.split(':') for x in buildentries]
    buildentries = [(os.path.splitext(os.path.basename(x[0]))[0], x[1]) for x in buildentry_parsed]

    if len(modentries) > 0:
        entry_points['iotile.proxy'] = ["{0} = {1}.{0}".format(x, tile.support_distribution) for x in modentries]
    if len(pluginentries) > 0:
        entry_points['iotile.proxy_plugin'] = ["{0} = {1}.{0}".format(x, tile.support_distribution) for x in pluginentries]
    if len(typelibs) > 0:
        entry_points['iotile.type_package'] = ["{0} = {1}.{0}".format(x, tile.support_distribution) for x in typelibs]
    if len(appentries) > 0:
        entry_points['iotile.app'] = ["{0} = {1}.{0}".format(x, tile.support_distribution) for x in appentries]
    if len(buildentries) > 0:
        entry_points['iotile.recipe_action'] = ["{1} = {2}.{0}:{1}".format(x[0], x[1], tile.support_distribution) for x in buildentries]

    data['name'] = tile.support_distribution
    data['package'] = tile.support_distribution
    data['version'] = tile.parsed_version.pep440_string()
    data['deps'] = ["{0} {1}".format(x.support_distribution, x.parsed_version.pep440_compatibility_specifier()) for x in _iter_dependencies(tile) if x.has_wheel]

    # If there are some python packages needed, we add them to the list of dependencies required
    if tile.support_wheel_depends:
        data['deps'] += tile.support_wheel_depends

    data['entry_points'] = entry_points

    outdir = os.path.dirname(str(target[0]))

    render_template('setup.py.tpl', data, out_path=str(target[0]))

    # Run setuptools to generate a wheel and an sdist
    curr = os.getcwd()
    os.chdir(outdir)
    try:
        setuptools.sandbox.run_setup('setup.py', ['-q', 'clean', 'sdist'])
        if "python_universal" in tile.settings:
            setuptools.sandbox.run_setup('setup.py', ['-q', 'clean', 'bdist_wheel', '--universal'])
        else:
            setuptools.sandbox.run_setup('setup.py', ['-q', 'clean', 'bdist_wheel'])
    finally:
        os.chdir(curr)
