# Release Notes

All major changes in each released version of IOTileBuild are listed here.

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
