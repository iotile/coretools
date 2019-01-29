"""Autobuilder plugin for creating a .ship archive from a yaml file.

This file is only meant to be used in conjunction with iotile-build and
should not be imported independently.  It is only for use inside SConstruct
files."""
import os
import imp
import inspect
from SCons.Script import Environment, Copy, Action
from iotile.build.build import ProductResolver, ArchitectureGroup
from iotile.build.utilities import render_template_inplace
from iotile.core.exceptions import BuildError
from ..recipe_manager import RecipeManager

def autobuild_shiparchive(src_file):
    """Create a ship file archive containing a yaml_file and its dependencies.

    If yaml_file depends on any build products as external files, it must
    be a jinja2 template that references the file using the find_product
    filter so that we can figure out where those build products are going
    and create the right dependency graph.

    Args:
        src_file (str): The path to the input yaml file template.  This
            file path must end .yaml.tpl and is rendered into a .yaml
            file and then packaged into a .ship file along with any
            products that are referenced in it.
    """

    if not src_file.endswith('.tpl'):
        raise BuildError("You must pass a .tpl file to autobuild_shiparchive", src_file=src_file)

    env = Environment(tools=[])

    family = ArchitectureGroup('module_settings.json')
    target = family.platform_independent_target()
    resolver = ProductResolver.Create()

    #Parse through build_step products to see what needs to imported
    custom_steps = []
    for build_step in family.tile.find_products('build_step'):
        full_file_name = build_step.split(":")[0]
        basename = os.path.splitext(os.path.basename(full_file_name))[0]
        folder = os.path.dirname(full_file_name)

        fileobj, pathname, description = imp.find_module(basename, [folder])
        mod = imp.load_module(basename, fileobj, pathname, description)
        full_file_name, class_name = build_step.split(":")
        custom_steps.append((class_name, getattr(mod, class_name)))
    env['CUSTOM_STEPS'] = custom_steps

    env["RESOLVER"] = resolver

    base_name, tpl_name = _find_basename(src_file)
    yaml_name = tpl_name[:-4]
    ship_name = yaml_name[:-5] + ".ship"

    output_dir = target.build_dirs()['output']
    build_dir = os.path.join(target.build_dirs()['build'], base_name)
    tpl_path = os.path.join(build_dir, tpl_name)
    yaml_path = os.path.join(build_dir, yaml_name)
    ship_path = os.path.join(build_dir, ship_name)
    output_path = os.path.join(output_dir, ship_name)

    # We want to build up all related files in
    # <build_dir>/<ship archive_folder>/
    # - First copy the template yaml over
    # - Then render the template yaml
    # - Then find all products referenced in the template yaml and copy them
    # - over
    # - Then build a .ship archive
    # - Then copy that archive into output_dir

    ship_deps = [yaml_path]

    env.Command([tpl_path], [src_file], Copy("$TARGET", "$SOURCE"))

    prod_deps = _find_product_dependencies(src_file, resolver)

    env.Command([yaml_path], [tpl_path], action=Action(template_shipfile_action, "Rendering $TARGET"))

    for prod in prod_deps:
        dest_file = os.path.join(build_dir, prod.short_name)
        ship_deps.append(dest_file)
        env.Command([dest_file], [prod.full_path], Copy("$TARGET", "$SOURCE"))

    env.Command([ship_path], [ship_deps], action=Action(create_shipfile, "Archiving Ship Recipe $TARGET"))
    env.Command([output_path], [ship_path], Copy("$TARGET", "$SOURCE"))


def _find_basename(input_file):
    base_src = os.path.basename(input_file[:-4])  # remove .tpl

    base_name, _base_ext = os.path.splitext(base_src)

    return base_name, base_src + ".tpl"


def _find_product_dependencies(src_file, resolver):
    resolver.start_tracking()
    render_template_inplace(src_file, {}, dry_run=True, resolver=resolver)

    products = resolver.end_tracking()
    return products


def template_shipfile_action(target, source, env):
    """Template a yaml ship recipe in place."""

    render_template_inplace(str(source[0]), {}, resolver=env["RESOLVER"])


def create_shipfile(target, source, env):
    """Create a .ship file with all dependencies."""

    source_dir = os.path.dirname(str(source[0]))
    recipe_name = os.path.basename(str(source[0]))[:-5]

    resman = RecipeManager()

    resman.add_recipe_actions(env['CUSTOM_STEPS'])
    resman.add_recipe_folder(source_dir, whitelist=[os.path.basename(str(source[0]))])
    recipe = resman.get_recipe(recipe_name)

    recipe.archive(str(target[0]))
