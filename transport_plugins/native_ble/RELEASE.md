# Release Notes

All major changes in each released version of the native BLE transport plugin are listed here.

## 3.1.0

- removed 3.6 support due to asyncio API change in 3.7
- Python 3.9 support

## 3.0.1

- Python compatibility set to 3.6-3.8 because of py35 EOL

## 3.0.0

- Temporarily remove `virtual_ble` interface as it is ported to be a DeviceServer.
- Update for compatibility with `iotile-core` 5.

## 2.0.3

- Implement proper dependency major version limits.

## 2.0.2

- Remove past/future/monotonic, pylint cleanup

## 2.0.1

- Drop python2 support

## 1.0.0

- Initial public release (only works on Linux)
