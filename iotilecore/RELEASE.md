# Release Notes

All major changes in each released version of `iotile-core` are listed here.

## 5.2.0

- removed deprecated `iotile.core.utilities.packed` module
- removed redistributed `intelhex` module
- removed duplicate of `typedargs` module from `utilities`
- removed support for python 3.6
- Python 3.9 support

## 5.1.5

- migrate from deprecated `imp` module to `importlib`
- Python compatibility set to 3.6-3.8 because of py35 EOL

## 5.1.4

- Fix memory leak in OperationManager

## 5.1.3

- Add new auth provider `InMemoryAuthProvider`. This allows users to
authenticate their device without CLI or environment variables
- Add registry support to temporarily set passwords for devices by uuid.

## 5.1.2

- Add support for an experimental, unstable `heartbeat` command in `HardwareManager`.  This
  command allows you to check if a DeviceAdapter is broken due to missing or nonresponsive
  hardware.  For it to work, the DeviceAdapter must the support the `heartbeat` debug command.

## 5.1.1

- Add the tqdm statusbar to the utc_assigner. There are some conditions where the binary 
  reports take a significant amount of time to process. A status bar helps show estimated time
  to process and show that code is not stalled.

## 5.1.0

- Remove dependency on sortedcontainers.  It was only used in one place and
  was preventing compiling CoreTools based applications using the ``nuitka``
  python compiler.  The specific use case in UTCAssigner was replaced with a
  focused implementation that also happened to be faster for our specific use
  case.

## 5.0.16

- Add hash algorithms to utilities
- Fix error handling in auth process

## 5.0.15

- Add `EnhancedReflashControllerRecord` to update scripts


## 5.0.14

- Add ability for `debug_manager` to flash `.bin` files
- Add a fix for "disconnect" command execution when connection to device is interrupted

## 5.0.13

- Add ability for iotile modules to create build_resource products

## 5.0.12

- Refactor OperationManager for usability.  It was designed to create maintainable networking
  code by abstracting away the common waiting patterns and allowing the creation of simple
  coroutines instead of complex callback based logic.
- Add shim to make `iotile-core` compatible with Python 3.8.0 on Windows.  There is a bug in
  that python version that breaks background event loops only on Windows.  It is fixed in
  python 3.8.1.
- Add new BLE broadcast encryption method: Encrypted with NullKey
- Update decryption logic for signed reports

## 5.0.11

- Fix missing Crypto dependency #919

## 5.0.10

- Add core authentication logic, authentication is conducted after the characteristics
  where probed as additional stage of connection
- Add auth provider to prompt user password
- Implement handshake routines
- Refactor auth providers, now it only manage access to key.
  Functions that encrypt/authenticate moved out to modules with particularly use them.
- Add reboot key and ephemeral key generation and verification

## 5.0.9

- Fix regression in the realtime streaming device

## 5.0.8

- Add ability to start periodic coroutines with the SharedLoop

## 5.0.7

- Add proxy matching with tile version

## 5.0.6

- Modify `watch_broadcasts` to treat individual UUID's streams as different items
- Modify parameters for `dump_memory` to use default addresses/lengths
- Fix double passing of BroadcastReports
- Fix logging error on task cancellation

## 5.0.5

- Fix TileBasedDevice controller override
- Update .pylintrc

## 5.0.4

- Augments the TileBasedDevice to respond to certain controller RPCs. It has the basic
  utilities from the tile_manager.
- Updates the event loop to have a more robust check for uncancelled tasks on shutdown

## 5.0.3

- `run_executor` can now be used in finalizer code

## 5.0.2

- Workaround bug in handling of RPCNotFound exception raised when a controller
  RPC is not found.  It was misraised as an application RPCError instead of
  RPCNotFound.

- Add required msgpack dependency that was incorrectly in `iotile-ext-cloud`
  although `iotile-core` had the dependency.

## 5.0.1

- Fix bug in utc_assigner.py that resulted in oscillating timestamp calculations

## 5.0.0

- Add support for background event loops using `asyncio` and migrate CMDStream
  DeviceAdapter interface.
- Refactor transport plugin system to use `asyncio` and add shim around legacy
  to use background event loop.
- Move all websockets code to `iotile-transport-websocket`.
- Completely remove `VirtualIOTileInterface` and replace with `AbstractDeviceServer`.
  `virtual_device` script has been updated to use `AbstractDeviceServer` directly instead
  of requiring it to be wrapped inside a `VirtualIOTileInterface` shim.
- Refactor virtual device hierarchy to be more maintainable and remove a lot of the
  legacy cruft that had accumulated in the machinery over the years.
- Standardize all hardware related exceptions inside `iotile.core.hw.exceptions`

## 4.1.2

- Add debug_interface read_memory() and write_memory() functions
- Integrate flash dump tool to read/dump data from flash, mapped, ram, external memory

## 4.1.1

- Implement proper dependency major version limits.

## 4.1.0

- Update UTCAssigner with more test coverage and add fix_report() method that
  will fix all readings inside of a SignedListReport with memoization to
  speed up the fixing process.

- Update UTCAssigner logic to check both directions from a reading to find out
  which part produces a more exact UTC timestamp, choosing the best one
  automatically.

- Update `IOTileReading` to do a better job of assigning itself a debug UTC
  time when it is created with an RTC timestamp value that can be directly
  converted to UTC without assumptions.

## 4.0.4

- Create async version of the ValidatingWSClient
- Create an EventLoop utility for managing asynchronous loops

## 4.0.3

- Remove remaining instances of builtins / __future__

## 4.0.2

- Remove past/future/monotonic, pylint cleanup

## 4.0.1

- Actually drop python2 support

## 4.0.0

- Drop python2 support
- This version was not officially released

## 3.27.2

- Fix support for `support_package` products in `IOTile` object and
  `ComponentRegistry`.

## 3.27.1

- Fix watch_broadcasts regression for non-bled112 configs

## 3.27.0

- Add support for `emulated_tile` product to be included in an IOTile Component.
  This is necessary now that `iotile-emulate` no longer supported python 2 and
  requires asyncio inside its emulated tiles.
- Change load_extensions so that when an exception on loading a module is
  raised it got caught and warning is logged in order to avoid breaking
  everything if there is an error importing an extension.
- Fix bug with sharing extensions between ComponentRegistry objects
- Fix error with multiple proxies with the same class name(#644)
- Fixup watch_broadcast notification for v1 (#673)
- Fix RPC v2 not checking argument boundaries (#676)


## 3.26.5

- Remove past.builtins dependency

## 3.26.4

- Fix regression sending an RPC over websockets v1 streams.

## 3.26.3

- Enable rpc_v2 for TileBusProxyPlugins

## 3.26.2

- Fix compatibility issue when searching for proxy plugins that should be
  filtered by component name.

## 3.26.1
- Update rpc_v2 mechanism to support "V" as a valid packing mechanism

## 3.26.0

- Support freezing the current list of extensions into a single file that is
  stored with the virtual environment, speeding up small program invocations
  by removing the necessity to enumerate all installed packages.

- Make log messages from virtual_device script less chatty by removing audit
  log messages by default.

- Remove nuisance log warning when loading extensions by name (Issue #637)

- Fix problem loading `module_settings.json` files for components that had been
  built before on python 3.  (Issue #636)

- Adds support for complex python support wheels in ComponentRegistry.
  Submodules inside the support package are now imported correctly so that
  relative imports among the modules work.

## 3.25.0

- Add support for a `__NO_EXTENSION__` flag in classes so that
  ComponentRegistry.load_extensions will ignore them.

- Add support for temporarily registering components without committing them to
  the persistent key-value store.

- Fix `iotile-updateinfo` to work without a -v flag.

## 3.24.4

- Consolidate entry point related code into ComponentRegistry with a single
  implementation of extension finding and importing.  Remove now redundant
  reimplementations of the same code.

- Fix support for STILL_PENDING flag in WorkQueueThread

- Update AsynchronousRPCResponse exception to not need an `__init__` argument.

- Fix verbosity argument for using virtual_device logging flag.

## 3.24.3

- Fix UTCAssigner to properly handle anchor streams and add support for decoding
  both RTC (y2k based) and epoch based timestamps.

## 3.24.2

- Add a better exception when the return value received from an RPC does not
  match the format that we expect.

- Add a workaround for a controller firmware bug so that CommandNotFound
  exceptions are properly raised when an RPC does not exist on the controller
  tile.

## 3.24.1

- Add 'show_rpcs' command line option to the iotile-updateinfo script to allow
  display of the actual RPCs in trub scripts.

## 3.24.0

- Remove unused RecordedStream class.
- Change RPC recording feature to save as a csv file instead of a json file.
- Add modern support for recording RPCs including runtime and status codes.

## 3.23.1

- Add support for generating semantic version range strings in a pep440
  compliant manner.  This generates a version specifier that is wider than the
  `~=` operator in pep440 when applied to versions that have a patch component.

## 3.23.0

- Add support into VirtualInterface for sending a callback when trace and report
  data is actually sent out of the VirtualInterface.  This is particularly
  useful for iotile-emulate so that it can provide back-pressure on various
  subsystems.  Previously, once a VirtualDevice queued a trace or report for
  transmission, it had no details on when it actually got sent.

- Add additional call to periodic_callback in AdapterStream to support the
  EmulatedDeviceAdapter better.

- Add support for passing premade DeviceAdapter classes into HardwareManager
  (Issue #545).  This is very useful for setting up complex test scenarios.

- Add support for WorkQueueThread to support dispatching work to background work
  queues and inserting sequence points where all prior work needs to be
  finished.

- Update WorkQueueThread to have a deferred_task function that will make an
  arbitrary callback once all current work items have been cleared.

- Update WorkQueueThread to be able to schedule a function to run once the
  work queue becomes idle.  There is a blocking and nonblocking version:
  wait_until_idle() and defer_until_idle(callback).

- Add UTCAssigner class to iotile.hw.reports for converting device uptime into
  absolute UTC time.

- Add a dependency of iotile-core on sortedcontainers distribution.

## 3.22.13

- Add "watch_reports" command, which enables a user to live view reports from
  the connected device
- Support for loading universal wheels
- Add Device slug to scan results

## 3.22.12

- SetDeviceTagRecord allows setting of both os and app tag.

## 3.22.11

- Fix Ctrl-C behavior of watch_broadcasts to not hang on exit sometimes and
  properly double buffer the display to remove the flickering.  Also update the
  UI at 50 ms rather than 500 ms to increase responsiveness.

## 3.22.10

- Add support for text mode websocket connections.  This is useful for
  connecting to mobile devices whose websockets servers don't implement binary
  mode.  It is autonegotiated between the client and server and prefers binary.

## 3.22.9

- Fix the registry function `list_config` so that the string 'config:' does not
  prefix each variable name in the list.

## 3.22.8

- FlashBoardStep uses shared resources

## 3.22.7

- Fix python 3 compatibility issues in ComponentRegistry and ValidatingWSClient.
  Now ValidatingWSClient will default to using unicode strings to encode command
  parameters.

## 3.22.6

- Fix python 3 compatibility issues

## 3.22.5
- Add connecting_string as optional arg to debug functions.
- FlashBoardStep now uses has optional debug_string for connection

## 3.22.4

- Make asciimatics an optional feature since it includes a large dependency
  on Pillow which requires compilation on linux.  Now, if you want the fancy
  command line ui, you need to install it using:
  `pip install iotilecore[ui]`

## 3.22.3

- Add function to ComponentRegistry to list all config variables

## 3.22.2

- Fix FlashBoardStep to have FILES variable so iotile-ship knows what files are
  needed to archive to .ship.

## 3.22.1

- Update device_updater app to reboot the device by default
- Update AdapterStream to better detect unicode strings incorrectly passed to
  send_highspeed on python 3.

## 3.22.0

- Add disconnection callback in ValidatingWSClient
- Set how ValidatingWSClient pack its message with msgpack
- Fix race condition in DeviceAdapter, which made awsiot and websockets tests
  failed sometimes
- Make send_highspeed working with Python3
- Add audit events for script interfaces
- Fix error in VirtualDevice which made interfaces never close

## 3.21.1

- Move SetDeviceTagRecord into iotile-core.
- Update device_updater app to be more robust in reconnecting to a device when
  running scripts that involve the device resetting itself multiple times.
- Update AdapterStream to allow multiple reconnection attempts when an RPC is
  set during an interrupted connection.

## 3.21.0

- Add support for a new module_settings.json format that has fewer levels of
  nesting.  The old format was designed for accommodating more than one module
  per file but we no longer support that so we don't need all of the extraneous
  dictionaries.  The IOTile class now supports parsing both kinds of files and
  stores some more information that is in different places in the two formats.

## 3.20.3

- Add `device_updater` app that allows you to run an update script on any
  iotile device.  Usage is: iotile hw app --name device_updater
- Additional python 3 compatibility fixes.

## 3.20.2

- Fix bug with undefined variable in external_proxy.py

## 3.20.1

- Add `python_depends` option in `module_settings.py` to install python
dependencies. (Issue #387)

## 3.20.0

- Minor python 3 compatibility adjustments on iotile-core
- Add support for UpdateScript and UpdateRecord objects to allow for creating
  device updating scripts directly via CoreTools
- Add iotile-updateinfo script that will print out everything that a `.trub`
  update file does.
- Update TileBusProxyObject to add support for hardware_version RPC calls.
- Add support for having components create custom build steps as part of their
  build products.

## 3.19.3

- Pass addition device_id parameter to IOTileApp subclasses so that they know
  what device they are talking to.

## 3.19.2

- Fix IOTile object to properly indicate that it has a support wheel even if
  the only thing in that wheel is an IOTileApp.

## 3.19.1

- Added RecipeAction FlashBoardStep. Used by iotile-ship
- Add support for IOTileEvent and FlexibleDictionaryReport objects to support
  handling complex data received from or generated on behalf of an IOTile
  device.

## 3.19.0

- Add support for IOTileApp objects that match the app tag on an iotile device
  and provide a high level API container for accessing functionality that is
  not just implemented by a single tile.  (Issue #303)
- Add support for waiting for a certain amount of tracing data like
  wait_reports.  (Issue #348)
- Cleanup the enable_streaming and enable_tracing code to allow it to be called
  multiple times per HardwareManager connection without breaking.

## 3.18.3

- Add support for generating PEP440 compliant version strings in
  SemanticVersion. (Issue #342)

## 3.18.2

- Optimized process_hex to return a list of section base addresses and section
  data to allow programming sections at a time.

## 3.18.1

- Add support for enable logging in the iotile tool.  This should be useful for
  debugging. (Issue #333)

## 3.18.0

- (Experimental) Include support for DebugManager that can take advantage of
  DeviceAdapters that provide a debug interface in order to reflash and/or
  download ram from attached devices, without requiring a functioning bootloader
  or other device support.

## 3.17.1

- Add in memory KV store option to ComponentRegistry that makes unit testing
  easier by preventing cross-contamination of settings.

## 3.17.0

- Migrate typedargs to a separate package for easier development and add
  dependency on that package.
- Make external type loading a lazy process to save startup time.

## 3.16.7

- Refactor creation/processing of ASCII command files into single utility class
  CommandFile since it is now being used across various packages.

## 3.16.6

- The tiles of a Tile Based virtual device can now access the device itself

## 3.16.5

- The tiles of a Tile Based virtual device can now access the device channel

## 3.16.4

- Follow symlinks if needed during the rename operation in JSONKVStore save
  method

## 3.16.3

- Add support for =X.Y.Z version range specifier in addition to the already
  supported ^X.Y.Z specifier.

## 3.16.2

- Add support for additional virtual_interface audit message then there is an
  error responding to an RPC that could not be corrected with a retry.

## 3.16.1

- Allow StoppableWorkerThread to have no timeout.  This allows for using
  generator functions that themselves wait for some external event and hence the
  extra sleep calls are superfluous.

## 3.16.0

- Add support for encrypting reports when a signing key is available.

## 3.15.3

- Add support for sorting scan results and limiting the number of results
  returned

## 3.15.2

- Add support for setting values in SparseMemory object.

## 3.15.1

- Improve the performance of ComponentRegistry by not rescanning all plugins
  every time it is loaded.

## 3.15.0

- Add support for tile modular tile based virtual devices with a new
  tile_based virtual device that allows you to configure what tiles it
  contains
- Add a VirtualTile class hierarchy to mirror the VirtualIOTileDevice
  class hierarchy

## 3.14.5

- Fix argument format on exception call inside virtualdevice

## 3.14.4

- Now using optional kwarg 'arg_format' in TileBusProxyObject's rpc method to
  allow calling code to not have to manually pack arguments

## 3.14.3

- Fix virtual device adapter to properly allow connecting to devices by setting
  the probe_required flag.

## 3.14.2

- Allow specifying sent streamer and timestamp when creating signed list reports

## 3.14.1

- Allow specifying the streamer selector and report id when creating signed list
  reports.

## 3.14.0

- Fix exception hierarchy to remove EnvironmentError and TimeoutError that
  shadow builtin exceptions

## 3.13.4

- Add better exception message when there are invalid arguments or response
  to a virtual device.

## 3.13.3

- Make StoppableThread stop faster when you configure a large interval for
  the thread function to run at.

## 3.13.2

- Add support for float validator

## 3.13.1

- Improve schema validator support

## 3.13.0

- Add support for validating documents using schema validator
- Add support for standard websocket client using schema validator
  to dispatch messages to handlers
- Add better support for virtaul virtual devices to allow realtime streaming
  of data from the devices rather than just on connection

## 3.12.4

- Fix handling of virtual interface config data that checked for the wrong
  dictionary key

## 3.12.3

- Add the ability to have configuration functions loaded in ConfigManager
  the same way that we have config variables.  This is needed by
  iotile-ext-cloud to support storing persistent cloud tokens.
- Increase test coverage

## 3.12.2

- Add the ability to load virtual devices from python modules that have not
  been installed using pip.  Just pass the path to the python file rather than
  the name of the pkg_resources entrypoint.  For example to load ./device.py
  as a virtual device, using iotile hw --port=virtual:./device.py

## 3.12.1

- Fix ConfigManager on tile proxy objects.  There was an infinite loop in
  list_variables and the other methods were poorly documented.

## 3.12.0

- Add support for ConfigManager that supports typed configuration variables
  that can be registered by coretools plugins.
- Fix nuisance exceptions in iotile shell when parameters are not convertable
  to their correct types.

## 3.11.0

- Add support for SparseMemory object that can use used to represent slices
  of memory downloaded from a device.  This is the first debug feature present
  in iotilecore.

## 3.10.3

- Remove debug print statement that got kept in released version

## 3.10.2

- Add support for forcing the registry to be a specific type; either json or
  sqlite are currently supported.  You can place a registry_type.txt file
  containing the word json or sqlite in the folder next to the
  component_registry.* file and it will choose json or sqlite based on what you
  put in the file throwing an error if a random word is entered.

## 3.10.1

- Add support for tracing from virtual devices over virtual interfaces

## 3.10.0

- Add support for a tracing interface.  The tracing interface allows sending an
  unstructured stream of debug data from an IOTile device and dumping it to
  stdout or a file using the iotile tool.

## 3.9.5

- Make scan wait for min_scan interval before returning if a HardwareManager is
  immediately created.  This fixes the same issue for scanning that could cause
  connections to fail.

## 3.9.4

- Allow KVStore to be backed by a JSON file or SQLite and add test coverage to
  make sure that ComponentRegistry, which is based on KVStore works correctly
  with both backing store types.

## 3.9.3

- Fix KVStore to not make a directory in user's home folder when iotile-core is
  installed in a virtual environment.

## 3.9.2

- Fix iotile script to not hang on exit if an uncaught exception happens and we
  are connected to a hardware device.

## 3.9.1

- Update virtual_device to be able to find devices in python files that are not
  installed. You just pass the path to the file rather than a name of an
  installed virtual device.

## 3.9.0

- Fix hash calculation to include footer in SignedListReport
- Add new functionality for waiting in AdapterStream until scanned devices are
  seen when connect is called for the first time.

## 3.8.1

- Fix bug finding TileBusProxyObject when a tile does not have any application
  firmware installed and add test coverage for this.

## 3.8.0

- Add support for AuthProviders that can sign/verify/encrypt/decrypt data.  This
  functionality is needed for verifying the signatures on reports received from
  the devices and creating signed reports.

- Add default ChainedAuthProvider that provides report signing and verifying
  using either SHA256 hashes (for integrity only) or HMAC-SHA256 using a key
  stored in an environment variable.

- Add support for running virtual_devices direcly without a loopback adapter.
  You can use the virtual:<device_name>@path_to_config_json connection string to
  connect to the device by its uuid.

- Add test coverage for signing and verifying reports.


## 3.7.0

- Add SignedList report format for streaming signed lists of multiple readings in
  a single report

## 3.6.2

- Add audit message for error streaming report

## 3.6.1

- Provide generic implementation of report chunking and streaming.

## 3.6.0

- Create a virtual device interface for serving access to virtual iotile devices
  that let people connect to computers like you connect to any other IOTile
  device.
- Add virtual_device script to make it easy to setup a virtual iotile device.

## 3.5.3

- Update IOTile to find component dependencies listed in architecture overlays
  as well as those listed for a module and for an architecture.

## 3.5.2

- Add the concept of coexistence classes to SemanticVersion objects so that you
  can easily see which are compatible with each other in a semanic versioning
  sense

## 3.5.1

- Add the ability to specify a key function to SemanticVersionRange.filter

## 3.5.0

- Add SemanticVersionRange object that supports defining basic ranges of
  semantic versions and checking if SemanticVersion objects are contained within
  them.  Currently only supports ^X.Y.Z ranges and * wildcard ranges.
- Properly parse the semantic version range specified in an IOTile component.

## 3.4.0

- Add support for sorting SemanticVersion objects and explicitly allow only a
  finite number of types of prereleases (build, alpha, beta and rc).  There is a
  total ordering of SemanticVersion objects where releases are better than
  prereleases and prereleases are ordered by build < alpha < beta < rc.  Each
  prerelease needs to be numbered like alpha1, rc5 etc.

## 3.3.0

- Add support for storing release steps in module_settings.json and parsing
  release steps in IOTile objects.  This will allow iotile-build and others to
  provide the ability to release built IOTileComponents for public or private
  distribution automatically.

## 3.2.0

- Add support for storing config settings in per virtualenv registry

## 3.1.1

- Add support for error checking in AdapterStream to catch errors connecting to
  a device or opening interfaces and convert them into HardwareErrors

## 3.1.0

- Add support for report streaming from IOTile devices through iotile-core and
  associated projects.

## 3.0.0

- Initial public release
