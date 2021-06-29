# Release Notes

All major changes in each released version of IOTileShip are listed here.

## 1.1.0

- removed 3.6 support due to asyncio API change in 3.7
- Python 3.9 support

## 1.0.10

- Python compatibility set to 3.6-3.8 because of py35 EOL

## 1.0.9

- Add ability for iotile modules to create build_resource products

## 1.0.8

- Fix py3 raw_input error in PromptStep
- Fix exception cleanup in recipe

## 1.0.7

- Unpin `iotile-core` to support iotile-core 5

## 1.0.6

- Added the FilesystemManager resource and ModifyJsonStep

## 1.0.5

- Implement proper dependency major version limits.

## 1.0.4

- Change open mode from 'rb' to 'r'.

## 1.0.3

- Remove remaining builtins/__future__

## 1.0.2

- Remove past/future/monotonic, pylint cleanup

## 1.0.1

- Drop python2 support

## 0.2.0

- Refactor extension importing system to use new
  ComponentRegistry.load_extensions() functionality provided by `iotile-core`.

## 0.1.5

- VerifyDeviceStep only checks os/app tags insteads of settings them

## 0.1.4

- Add SyncRTCStep to set the RTC to current UTC time.

## 0.1.3

- Add connect_direct as HardwareManagerResource RESOURCE_ARG_SCHEMA optional argument.
- autobuild_shiparchive adds build_steps as needed.

## 0.1.2

- SyncCloudStep has overwrite parameter default to False. Set to True if
  cloud settings should be changed.
- VerifyDeviceStep uses shared resources

## 0.1.1

- HardwareManagerResource checks if connect_id is None before parsing it.
  Also added connect_direct as an option


## 0.1.0

- Refactor to allow for shared resources to be used across action steps
- Improve python 3 compatibility
- Add support for sending a TRUB script as a step.
- Add support for autodetecting which variables need to be passed and which
  are optional.
- Improve printing of recipes to include information on required and free
  variables.
- Allow creation and use of .ship archives which are recipe files along with
  all external files they depend on in a single zip that can be distributed and
  used.

## 0.0.1

- First Release. First definitions of RecipeObjects, RecipeActionObjects, and
  RecipeManager.
- Console script iotile-ship. Params include uuid, config file input, range,
  preserve temp files
- PromptStep, WaitStep, PipeSnippetStep, VerifyDeviceStep, SyncCloudStep
