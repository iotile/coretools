# Release Notes

All major changes in each released version of the iotile-ext-cloud plugin are listed here.

## 0.5.0

- Make python 3 compatible and release on python 2 and python 3.

## 0.4.7

- Refactor cloud.utilities to use iotile_cloud.utils.gid.IOTileCloudSlug classes

## 0.4.6

- Fix set_device_template to use staff priveledge to set device_template
- Fix @param for app_tag in set_sensorgraph

## 0.4.5

- Fix compatibility with new IOTileApp `__init__` signature.

## 0.4.4

- Improve cloud_uploader to continue downloading reports even if the manually
  triggered streamer did not have any new data.

## 0.4.3

- Add support for uploading FlexibleDictionaryReport to iotile.cloud.

## 0.4.2

- Update cloud_uploader app to have a function that just downloads reports
  without uploading them to the cloud.  This is useful for reusing this app's
  functionality in other apps.

## 0.4.1

- Add function to get all streamers for a given device

## 0.4.0

- Include cloud_uploader app that can upload data from any standard streaming
  device to iotile.cloud.  Usage is:
  iotile hw connect <UUID> app --name cloud_uploader upload

## 0.3.7

- Rerelease of 0.3.6
- Version 0.3.6 doesn't exist on pypi.


## 0.3.6

- Add support for changing device templates. 
- Check if device template and sensorgraph has correct os/app tags

## 0.3.5

- Add support for permanent device tokens

## 0.3.4

- Bugfix for empty whitelist scenario

## 0.3.3

- Support for whitelists and fleets

## 0.3.2

- Added another utility function

## 0.3.1

- Start adding common utility functions

## 0.3.0

- Add the ability to autologin to iotile.cloud if the user is in an interactive session
  and they don't have stored cloud credentials.  We will prompt for a username/password
  on the command line.

## 0.2.3

- Modified device lookup to conditionally filter by project or not

## 0.2.2

- Fix jwt token refresh to work on non default iotile.cloud servers.

## 0.2.1

- Add cloud:server config variable for configuring different domains for talking to iotile.cloud.
  This allows for dev, test and staging servers to be setup and CoreTools pointed at them.

## 0.2.0

- Rename exceptions for better compatibility

## 0.1.1

- Improved documentation

## 0.1.0

- Initial public release
