# Release Notes

All major changes in each released version of the bled112 transport plugin are listed here.

## 1.7.3

- Add support for broadcast readings in virtual bled112 interface.  Now if you
  stream BroadcastReport objects from a virtual device over bled112, it will 
  properly update the advertising scan response data to contain the reading
  value.

## 1.7.2

- Resolve additional issue with rpc response not being bytes when an exception
  occurs.

## 1.7.1

- Resolve issue with advertising data and rpc responses for virtual devices on
  python 3.

## 1.7.0

- Add support for python 3.
- Refactor logging statements to make it easier to log from the bled112 module
  and remove extra chatty log messages.

## 1.6.1

- Remove extraneous, verbose debug log statement.

## 1.6.0

- Add bled112-v1-6-0-virtual.hex into blob.
- Add support for pushing broadcast readings received as part of scan response
  data.

## 1.5.2

- Clean code and improve compatibility with Python3

## 1.5.1

- Fix bug in virtual_interface that could crash if a client disconnected when an RPC was
  in flight. (#283)

## 1.5.0

- Add support for a config variable bled112:active-scan that performs active scans and returns
  more data about discovered devices.

## 1.4.8

- Adjust stop check interval for virtual bled112 interface that needs a faster check time

## 1.4.7

- Add a configuration option for the interval with which the BLEDCMDProcessor thread checks
  for a stop flag.  This allows lowering CPU usage in production settings while still keeping
  tests fast.

## 1.4.6

- Fix initialization that can hang if a previous process exited uncleanly without
  stopping scanning.  Now we gratuitously stop scanning on dongle initialization. (#231)

## 1.4.5

- Added helper method to BLED112Adapter for safely removing connections
- Modified BLED112Adapter's _get_connection for safer connection lookups, modified calling code to handle empty response

## 1.4.4

- Update exception hierarchy

## 1.4.3

- Add advertisement flag that we support fast write without response actions on our RPC interface.

## 1.4.2

- Clean up streaming interface when a client disconnects so that we stream again
  to future clients.

## 1.4.1

- Add support for tracing from virtual bled112 interface for testing and logging from virtual devices

## 1.4.0

- Add preliminary support for tracing interface.  BLED112 adapter now supports the tracing interface.  

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