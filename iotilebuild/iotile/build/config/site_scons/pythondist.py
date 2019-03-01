"""Functions for building a python support wheel."""

import os.path
import os
import sys
import glob
import subprocess
import setuptools.sandbox

from SCons.Script import *
from docbuild import *
from release import *
from dependencies import find_dependency_wheels, _iter_dependencies
from iotile.build.utilities import render_template
from iotile.core.exceptions import *


ENTRY_POINT_MAP = {
    'build_step': 'iotile.recipe_action',
    'app_module': 'iotile.app',
    'proxy_module': 'iotile.proxy',
    'emulated_tile': 'iotile.emulated_tile',
    'type_package': 'iotile.type_package',
    'proxy_plugin': 'iotile.proxy_plugin',
    'virtual_tile': 'iotile.virtual_tile',
    'virtual_device': 'iotile.virtual_device'
}


def get_support_package(tile):
    """Returns the support_package product."""

    packages = tile.find_products('support_package')
    if len(packages) == 0:
        return None
    elif len(packages) == 1:
        return packages[0]

    raise BuildError("Tile declared multiple support packages, only one is supported", packages=packages)


def iter_support_files(tile):
    """Iterate over all files that go in the support wheel.

    This method has two possible behaviors.  If there is a 'support_package'
    product defined, then this recursively enumerates all .py files inside
    that folder and adds them all in the same hierarchy to the support wheel.

    If there is no support_package product defined, then the old behavior
    takes over, where all files containing python entrypoints are iterated
    over using iter_python_modules() and they are copied into the support
    wheel and then an __init__.py file is added.

    The files are yielded as tuples of (copy_name, input_path).
    """

    support_package = get_support_package(tile)
    if support_package is None:
        for module, _, _ in iter_python_modules(tile):
            yield os.path.basename(module), module
    else:
        for dirpath, _dirnames, filenames in os.walk(support_package):
            for filename in filenames:
                if not filename.endswith('.py'):
                    continue

                input_path = os.path.join(dirpath, filename)
                output_path = os.path.relpath(input_path, start=support_package)

                if output_path == "__init__.py":
                    continue

                yield output_path, input_path


def iter_python_modules(tile):
    """Iterate over all python products in the given tile.

    This will yield tuples where the first entry is the path to the module
    containing the product the second entry is the appropriate
    import string to include in an entry point, and the third entry is
    the entry point name.
    """

    for product_type in tile.PYTHON_PRODUCTS:
        for product in tile.find_products(product_type):
            entry_point = ENTRY_POINT_MAP.get(product_type)
            if entry_point is None:
                raise BuildError("Found an unknown python product (%s) whose entrypoint could not be determined (%s)" %
                                 (product_type, product))

            if ':' in product:
                module, _, obj_name = product.rpartition(':')
            else:
                module = product
                obj_name = None

            if not os.path.exists(module):
                raise BuildError("Found a python product whose path did not exist: %s" % module)

            product_name = os.path.basename(module)
            if product_name.endswith(".py"):
                product_name = product_name[:-3]

            import_string = "{} = {}.{}".format(product_name, tile.support_distribution, product_name)

            if obj_name is not None:
                import_string += ":{}".format(obj_name)

            yield (module, import_string, entry_point)


def build_python_distribution(tile):
    env = Environment(tools=[])

    builddir = os.path.join('build', 'python')
    packagedir = os.path.join(builddir, tile.support_distribution)
    outdir = os.path.join('build', 'output', 'python')
    outsrcdir = os.path.join(outdir, 'src')

    if not tile.has_wheel:
        return

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


    for outpath, inpath in iter_support_files(tile):
        outfile = os.path.join(outsrcdir, outpath)
        buildfile = os.path.join(packagedir, outpath)

        target = env.Command(outfile, inpath, Copy("$TARGET", "$SOURCE"))
        env.Depends(target, outsrcnode)

        target = env.Command(buildfile, inpath, Copy("$TARGET", "$SOURCE"))
        env.Depends(target, pkg_init)

        buildfiles.append(buildfile)

    # Create setup.py file and then use that to build a python wheel and an sdist
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

    # Also copy over all dependency wheels as well
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

    entry_points = {}

    for _mod, import_string, entry_point in iter_python_modules(tile):
        if entry_point not in entry_points:
            entry_points[entry_point] = []

        entry_points[entry_point].append(import_string)

    data['name'] = tile.support_distribution
    data['package'] = tile.support_distribution
    data['version'] = tile.parsed_version.pep440_string()
    data['deps'] = ["{0} {1}".format(x.support_distribution, x.parsed_version.pep440_compatibility_specifier())
                    for x in _iter_dependencies(tile) if x.has_wheel]

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


def run_pytest(target, source, env):
    """Run pytest, saving its log output to the target file."""

    try:
        return_value = 0
        output = subprocess.check_output(['pytest', str(source[0])], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as err:
        output = err.output
        return_value = err.returncode

        print(output.decode('utf-8'))

    with open(str(target[0]), "wb") as outfile:
        outfile.write(output)

    return return_value
