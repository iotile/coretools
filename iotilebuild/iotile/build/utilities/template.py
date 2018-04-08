# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

#template.py
#Utilities for producing skeleton code for application modules, unit tests,
#etc. using the Cheetah templating library.

import os.path
from future.utils import viewitems
import os
import shutil
from past.builtins import basestring
from pkg_resources import resource_filename, Requirement
from jinja2 import Environment, PackageLoader, FileSystemLoader
from typedargs.exceptions import ArgumentError


def render_template_inplace(template_path, info, dry_run=False, extra_filters=None, resolver=None):
    """Render a template file in place.

    This function expects template path to be a path to a file
    that ends in .tpl.  It will be rendered to a file in the
    same directory with the .tpl suffix removed.

    Args:
        template_path (str): The path to the template file
            that we want to render in place.
        info (dict): A dictionary of variables passed into the template to
            perform substitutions.
        dry_run (bool): Whether to actually render the output file or just return
            the file path that would be generated.
        extra_filters (dict of str -> callable): An optional group of filters that
            will be made available to the template.  The dict key will be the
            name at which callable is made available.
        resolver (ProductResolver): The specific ProductResolver class to use in the
            find_product filter.

    Returns:
        str: The path to the output file generated.
    """

    filters = {}
    if resolver is not None:
        filters['find_product'] = _create_resolver_filter(resolver)

    if extra_filters is not None:
        filters.update(extra_filters)

    basedir = os.path.dirname(template_path)
    template_name = os.path.basename(template_path)

    if not template_name.endswith('.tpl'):
        raise ArgumentError("You must specify a filename that ends in .tpl", filepath=template_path)

    out_path = os.path.join(basedir, template_name[:-4])

    if basedir == '':
        basedir = '.'

    env = Environment(loader=FileSystemLoader(basedir),
                      trim_blocks=True, lstrip_blocks=True)

    # Load any filters the user wants us to use
    for name, func in viewitems(filters):
        env.filters[name] = func

    template = env.get_template(template_name)
    result = template.render(info)

    if not dry_run:
        with open(out_path, 'wb') as outfile:
            outfile.write(result.encode('utf-8'))

    return out_path


def render_template(template_name, info, out_path=None):
    """Render a template using the variables in info.

    You can optionally render to a file by passing out_path.

    Args:
        template_name (str): The name of the template to load.  This must
            be a file in config/templates inside this package
        out_path (str): An optional path of where to save the output
            file, otherwise it is just returned as a string.
        info (dict): A dictionary of variables passed into the template to
            perform substitutions.

    Returns:
        string: The rendered template data.
    """

    env = Environment(loader=PackageLoader('iotile.build', 'config/templates'),
                      trim_blocks=True, lstrip_blocks=True)

    template = env.get_template(template_name)
    result = template.render(info)

    if out_path is not None:
        with open(out_path, 'wb') as outfile:
            outfile.write(result.encode('utf-8'))

    return result


def render_recursive_template(template_folder, info, out_folder, preserve=None, dry_run=False):
    """Copy a directory tree rendering all templates found within.

    This function inspects all of the files in template_folder recursively. If
    any file ends .tpl, it is rendered using render_template and the .tpl
    suffix is removed.  All other files are copied without modification.

    out_folder is not cleaned before rendering so you must delete its contents
    yourself if you want that behavior.

    If you just want to see all of the file paths that would be generated,
    call with dry_run=True.  This will not render anything but just inspect
    what would be generated.

    Args:
        template_folder (str): A relative path from config/templates with the
            folder that should be rendered recursively.
        info (dict): A dictionary of variables to be substituted into any
            templates found in template_folder.
        out_folder (str): The path to the output folder where the template will
            be generated.
        dry_run (bool): Whether to actually render output files or just return
            the files that would be generated.
        preserve (list of str): A list of file names relative to the start of the
            template folder that we are rendering that end in .tpl but should not
            be rendered and should not have their .tpl suffix removed.  This allows
            you to partially render a template so that you can render a specific
            file later.

    Returns:
        dict, list: The dict is map of output file path (relative to
            out_folder) to the absolute path of the input file that it depends
            on. This result is suitable for using in a dependency graph like
            SCons. The list is a list of all of the directories that would need
            to be created to hold these files (not including out_folder).
    """

    if isinstance(preserve, basestring):
        raise ArgumentError("You must pass a list of strings to preserve, not a string", preserve=preserve)

    if preserve is None:
        preserve = []

    preserve = set(preserve)

    template_dir = os.path.join(resource_filename(Requirement.parse("iotile-build"), "iotile/build/config/templates"))
    indir = os.path.abspath(os.path.join(template_dir, template_folder))

    if not os.path.exists(indir):
        raise ArgumentError("Input template folder for recursive template not found", template_folder=template_folder, absolute_path=indir)
    elif not os.path.isdir(indir):
        raise ArgumentError("Input template folder is not a directory", template_folder=template_folder, absolute_path=indir)

    create_dirs = []
    file_map = {}

    # Walk over all input files
    for dirpath, dirs, files in os.walk(indir):
        for file in files:
            in_abspath = os.path.abspath(os.path.join(dirpath, file))
            in_path = os.path.relpath(os.path.join(dirpath, file), start=indir)

            if file.endswith(".tpl") and not in_path in preserve:
                out_path = in_path[:-4]
            else:
                out_path = in_path

            file_map[out_path] = (in_path, in_abspath)

            for folder in dirs:
                dir_path = os.path.relpath(os.path.join(dirpath, folder), start=indir)
                create_dirs.append(dir_path)

    # Actually render / copy all files if we are not doing a dry run
    if not dry_run:
        for folder in create_dirs:
            out_path = os.path.join(out_folder, folder)
            if not os.path.isdir(out_path):
                os.makedirs(out_path)

        for out_rel, (in_path, in_abspath) in viewitems(file_map):
            out_path = os.path.join(out_folder, out_rel)
            if in_path in preserve or not in_path.endswith(".tpl"):
                shutil.copyfile(in_abspath, out_path)
            else:
                # jinja needs to have unix path separators regardless of the platform and a relative path
                # from the templates base directory
                in_template_path = os.path.join(template_folder, in_path).replace(os.path.sep, '/')
                render_template(in_template_path, info, out_path=out_path)

    return file_map, create_dirs


def _create_resolver_filter(resolver):
    def _resolver(product_id):
        product_class, name = product_id.split(',')

        product_class = product_class.strip()
        name = name.strip()

        return resolver.find_unique(product_class, name).short_name

    return _resolver
