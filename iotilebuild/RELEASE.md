# Release Notes

All major changes in each released version of IOTileBuild are listed here.

## 3.0.3

- Remove past/future/monotonic, pylint cleanup

## 3.0.1

- Drop python2 support

## 2.8.1

- Add support for `emulated_tile` product to `iotile build`.

## 2.8.0

- Add support for complex python support wheels where there is an actual 
  python package present in `python/support`.  Makes sure that the 
  python package contents are properly copied into the output support wheel.

- Refactor to remove all references to `pkg_resources`.  Uses centralized 
  entrypoint loading system from iotile.core instead.

- Fix additional python 3 incompatibilities with `iotile build` that prevented
  builds from running correctly on python 3.
 
## 2.7.0

- Add support for running pytest unit tests as part of the build process.
- Refactor python support wheel building process to accommodate additional
  python products and increase test coverage of the wheel generation process.

## 2.6.17

- Add disable/reenable sensorgraph to safely reflash firmware

## 2.6.16

- Update TRUB script autobuilder to add a 'use_safemode' option. If this option
  is set to True in a build_update_script() call or an autobuild_trub_script
  call, then the firmware load records in the TRUB script will be sandwiched
  between SendRPCRecords enabling and then disabling safemode.

## 2.6.15

- Fix #514, widens the versions of dependencies specified in install_requires
  for dependent wheels to be compatible with semantic versioning.  Previously
  versions were pinning to have the same minor release number, now they are
  just pinned to have the same major version number.

## 2.6.14

- Add update_local to DepedencyManager(). This allows updating any local dependencies of
a component without updating all the other dependencies. 

## 2.6.13

- Enable using iotile build to generate py3 packages and universal wheels

## 2.6.12

- Fix build_update_script, env['SLOTS'] to None by default.

## 2.6.11

- Fix autobuild_trub_script, check env['UPDATE_SENSORGRAPH'] if sensorgraph needs to be updated. 
- For now, app and os tags are seperate records. Combine with an iotile-core fix.

## 2.6.10

- autobuild_trub_script(file_name, slot_assignments=None, os_info=None, sensor_graph=None, app_info=None)

## 2.6.9

- Add architecture overrides for qemu unit tests so that they target the
  cortex-m0plus

## 2.6.8

- Add list_local to DependencyManager so that we can implement a recursive build
  system that knows to build local dependencies first  before building a
  component that depends on them.

## 2.6.7

- Add qemu testing to continuous integration on linux
- Fix semihost.c template to properly mark svc params as volatile in order to
  prevent recent gcc versions from optimizing them out.

## 2.6.6

- Fix unit test generation to properly copy over referenced C modules and all
  potentially useful header files.

## 2.6.5

- Fix regression building firmware with tilebus_definition or
  include_directories (Issue #433)

## 2.6.4

- Fix most python 3 compatibility issues.
- Add support for copying release notes into output

## 2.6.3

- Improve template generation to allow for finding products and using their
  paths in a template.

## 2.6.2
- Fix bug when building on Mac OSX where parentheses required quotes in a
  commandline. 

## 2.6.1

- Add support for hiding the firmware images contained in dependency tiles
- Add a ProductResolver class that can find products of dependencies or the
  current tile being built.  This allows specifying products by name and having
  them automatically resolved to the correct path.
- Fix autobuild_bootstrap to use intermediate folder so that all intermediate
  build products are inspectable and not generated directly in build/output.
- Add autobuild_trub_script function that can generate OTA scripts given a list
  of firmware images to assign to tiles.

## 2.6.0

- Add support for a new module_settings.json format that has fewer levels of
  nesting.  The old format was designed for accommodating more than one module
  per file but we no longer support that so we don't need all of the extraneous
  dictionaries.
- Add support for running semihosted unit tests on qemu.
- Update embedded scons to 3.0.1 for python 3 compatibility.

## 2.5.12

- Fix naming of custom build steps

## 2.5.11

- Fix support for building custom build steps

## 2.5.10

- Add python dependencies given in the `python_depends` option in module_settings.json, to the
`install_requires` in setup.py, to indicate python package needed. (Issue #387)

## 2.5.9

- Add support for building custom build_steps in python support wheels.

## 2.5.8

- autobuild_bootstrap_file creates only one command so that temporary hex files
  are not actual targets.

## 2.5.7

- Fix regression in command_map_c.h.tpl that incorrectly assigned version 
  numbers to firmware.

## 2.5.6

- Fix setup.py template to include subpackages as well in the final 
  support distribution.

## 2.5.5

- Fix generation of setup.py for wheel building to properly reference complete
  version number.
- Add basic iotile-emulate script for running an elf on qemu. (Experimental)

## 2.5.4

- merge_hex_executables now sets IntelHex start_addr to None to prevent error throwing during merge.

## 2.5.3

- Rerelease of 2.5.2

## 2.5.2

- Add autobuild_bootstrap_file to combine firmware files into a single bootstrap product (Issue #350)

## 2.5.1

- Add support for including app modules in components and support packages. 
  App modules are like proxies but apply to an entire device rather than just
  a single tile.  (Issue #303)

## 2.5.0 

- Add support for releasing python packages to pypi as a release_step
- Refactor tilebus compiler support to clean up old cruft
- Add standalone iotile-tbcompile program to provide access to information
  inside the .bus files. (Issue #340)
- Add support for prerelease python packages.  (Issue #342)

## 2.4.5

- Fix support for config variable arrays and add support for encoded binary values

## 2.4.4

- Add support for reading config variable arrays and writing them properly into config_variables_c.c

## 2.4.3

- Fix powershell issue with Sphinx that causes the terminal colors to be
  inverted after iotile build

## 2.4.2

- Fix template compatability issue for Cheetah #242.

## 2.4.1

- Rename exceptions for compatibility

## 2.4.0

- Add support for showing build commands during builds by setting the build:show-commands
  config variable. 

## 2.3.0

- Add support for pull command and pull_release inside of DependencyResolverChain to
  manually pull and unpack a released component version by name and version

## 2.2.8

- Add explicit dependency on setuptools and wheel to make sure we have the bdist_wheel
  commmand.

## 2.2.7

- Update build system to allow modules to specify architecture overlays, not just other
  architectures. 

## 2.2.6

- Update autobuild_release to allow it to be called manually from an SConstruct file

## 2.2.5

- Fix bug building components that specified a version for their dependencies
- Add extensive test coverage of dependency resolution
- Update with dependency check function to test and make sure all installed dependencies
  are compatible with each other.

## 2.2.4

- Update RegistryResolver to properly check the version of the component it found in the registry
  to make sure that it matches.

## 2.2.3

- Fix DependencyResolverChain to properly report when its updating vs installing a new component

## 2.2.2

- Fix bug in DependencyResolverChain where checking if a component is up to date didn't work
  if there were multiple dependency resolvers in the chain.

## 2.2.1

- Update iotile release to make the path optional
- Update docstring for DependencyResolver

## 2.2.0

- Add entry point for inserting release providers that allow releasing IOTile components.
- Add iotile release command for releasing an IOTile using a sequence of release providers
- Update minimum required iotile-core version to 3.3.0 based on the need for release_steps
  parsing in the IOTile object.

## 2.1.0

- Add entry point for inserting DependencyResolvers into the lookup chain
  used to find dependencies for a tile.  The entry point is iotile.build.depresolver.
  See iotile.build.dev.resolvers.__init__.py for the entry point format
- Add DependencyResolverChain unit test
- Add missing dependency on toposort

## 2.0.5

- Improve error processing in dependencies with documentation (Issue #48)

## 2.0.4

- Fix error processing dependencies in documentation (Issue #48)
