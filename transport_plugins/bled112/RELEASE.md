# Release Notes

All major changes in each released version of the bled112 transport plugin are listed here.

## 1.3.6

- Add error checking and automatic retry for Early Disconnect bluetooth errors.  Previously,
  these errors were just reported to the user as if the device could not be connected to, however,
  per the Bluetooth spec, these errors are expected 1-2% of the time so we now automatically retry
  the connection up to 5 times.

## 1.3.5

- Send on_disconnect events when disconnects occur even outside of RPC processing

## 1.3.4

- Support reconnecting to a device if it resets midconnection
- Support a minimum scan interval before connect will work so that we always wait to receive advertisements
  before saying we couldn't find a devie (this is mainly implemented in AdapterStream but a config setting
  comes from the DeviceAdapter)

## 1.3.3

- BLE backoff did not properly resend chunks that had an error, instead it just dropped them, leading
  to data corruption.

## 1.3.2

- Fix ble backoff on notification to properly back off when the client cannot keep up with data streaming

## 1.3.1

- Catch errors streaming reports in virtual device and don't choke, instead stop streaming reports
  and log an audit message.

## 1.3.0

- Include the ability to stream reports

## 1.2.0

- Update to include virtual interface for serving access to virtual iotile device over bled112

## 1.1.1

- Add more robust error checking with a nice message if the connection disconnects unexpectedly

## 1.1.0

- Support report streaming from IOTile devices
- Improve unit test coverage

## 1.0.0

- Initial public release