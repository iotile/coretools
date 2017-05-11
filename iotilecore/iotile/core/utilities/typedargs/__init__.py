"""Glue package shim to keep imports working since typedargs was broken into new package."""

import pkg_resources


# Recreate all old imports
from typedargs.annotate import param, returns, context, finalizer, takes_cmdline, annotated, return_type, stringable
from typedargs.typeinfo import type_system, iprint

def load_external_components():
    """Load all external typed defined by iotile plugins.

    This allows plugisn to register their own types for type annotations and
    allows all registered iotile components that have associated type libraries to
    add themselves to the global type system.
    """

    # Find all of the registered IOTile components and see if we need to add any type libraries for them
    from iotile.core.dev.registry import ComponentRegistry

    reg = ComponentRegistry()
    modules = reg.list_components()

    typelibs = reduce(lambda x, y: x+y, [reg.find_component(x).type_packages() for x in modules], [])
    for lib in typelibs:
        if lib.endswith('.py'):
            lib = lib[:-2]

        type_system.load_external_types(lib)

    # Also search through installed distributions for type libraries
    for entry in pkg_resources.iter_entry_points('iotile.type_package'):
        mod = entry.load()
        type_system.load_type_module(mod)


load_external_components()
