# Release Notes

All major changes in each released version of IOTileTest are listed here.

## 0.7.0

- Add test virtual device tracing_test for testing the tracing interface of iotile-core

## 0.6.3

- Update prepare_device to have the correct number of successful vs total devices seen

## 0.6.2

- Update prepare_device to default to no retries since most errors are unrecoverable
- Update script execution to use module importing since that captures globals correctly

## 0.6.1

- Bug fix where uuid_range was invalid if not specified on the command line

## 0.6.0

- Add pytest fixtures for running hardware tests on devices
- Add prepare_device script for running a script that prepares a device into a
  known state

## 0.5.3

- Fix device id processing to process strings as hex in report_test device and
  add support for configuring more details about how the reports are generated.
- Allow the creation of reports with no readings for testing.

## 0.5.2

- Add no_app test device for testing TileBusProxyObject

## 0.5.1

- Update report_test device to support SignedListReport types and report signing

## 0.5.0

- Update invidual_reports device to report_test device and add support for SignedList
  report type.

## 0.4.2

- Allow iotile ids to be specified as hex strings or integers

## 0.4.1

- Fix invidiual_reports device to respect iotile_id argument.

## 0.4.0

- Include the ability to stream reports and create individual_reports virtual
  test device.

## 0.3.0

- Include simple virtual device and simple proxy for testing virtual device
  interface.

## 0.2.0

- Mock dependency resolver object for testing dependency resolution process
  in iotile-build

## 0.1.0

- Initial support for a MockIOTileDevice object
- Initial support for a MockBLEDevice object that uses MockIOTileDevice
- Initial public release
