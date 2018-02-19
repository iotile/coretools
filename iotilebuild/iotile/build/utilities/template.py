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
import os
import shutil
from pkg_resources import resource_filename, Requirement
from jinja2 import Environment, PackageLoader
from typedargs.exceptions import ArgumentError


def render_template(template_name, info, out_path=None):
    """Render a template based on this TileBus Block.

    The template has access to all of the attributes of this block as a
    dictionary (the result of calling self.to_dict()).

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
            outfile.write(result)

    return result


def render_recursive_template(template_folder, info, out_folder, dry_run=False):
    """Copy a directory tree rendering all templates found within.

    This function inspects all of the files in template_folder recursively.
    If any file ends .tpl, it is rendered using render_template and the
    .tpl suffix is removed.  All other files are copied without modification.

    out_folder is not cleaned before rendering so you must delete its contents
    yourself if you want that behavior.

    If you just want to see all of the file paths that would be generated, call
    with dry_run=True.  This will not render anything but just inspect what would
    be generated.

    Args:
        template_folder (str): A relative path from config/templates with the
            folder that should be rendered recursively.
        info (dict): A dictionary of variables to be substituted into any
            templates found in template_folder.
        out_folder (str): The path to the output folder where the template will
            be generated.
        dry_run (bool): Whether to actually render output files or just return
            the files that would be generated.

    Returns:
        dict, list: The dict is map of output file path (relative to
            out_folder) to the absolute path of the input file that it depends
            on. This result is suitable for using in a dependency graph like
            SCons. The list is a list of all of the directories that would need
            to be created to hold these files (not including out_folder).
    """

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

            if file.endswith(".tpl"):
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

        for out_rel, (in_path, in_abspath) in file_map.iteritems():
            out_path = os.path.join(out_folder, out_rel)
            if not in_path.endswith(".tpl"):
                shutil.copyfile(in_abspath, out_path)
            else:
                # jinja needs to have unix path separators regardless of the platform and a relative path
                # from the templates base directory
                in_template_path = os.path.join(template_folder, in_path).replace(os.path.sep, '/')
                render_template(in_template_path, info, out_path=out_path)

    return file_map, create_dirs
