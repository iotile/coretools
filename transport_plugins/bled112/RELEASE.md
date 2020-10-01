# Release Notes

All major changes in each released version of the bled112 transport plugin are listed here.

## 3.0.8

- Added a connection map consisting of devices' connection string and uuid
to the `BLED112Adapter`
- Callback `on_authentication_check_response` uses calls `authenticate` with device UUID instead of MAC
- Authentication function does basic check if UUID is valid
 - Fix typos

## 3.0.7

- Correct indicator flags for Broadcast v2 advertisements

## 3.0.6

- Add dongle removal detection logic that sets the `stopped` property.
- Add a `heartbeat` debug command that checks if the dongle is currently alive.
- Prevent API calls from hanging if a dongle is removed in the middle of an API call such
  as connect or send_rpc.  Previously the call would never complete.  Now the call fails
  with an exception.

## 3.0.5

- Add optional deduplication of broadcast-V2 formatted Advertising packets 
- Add `safe_mode` advertisement flag in scan results

## 3.0.4

- Refactor BLE broadcast encryption flags: three bits are treated as an enumeration
- Consilidate two authentication characteristics into one
- Update info characteristic
- Remove separate logic for NullKey encryption temp key generation, the temp key is
  generated the same way it is done for user key
- Add the password-based authentication method
- Update the authentication flow
- Disable "RPC in progress" check
- Fix event handling for "Encrypt start" cmd

## 3.0.3

- Fix bled112_auth error handling

## 3.0.2

- Add core authentication logic, authentication is conducted after the characteristics
  where probed as additional stage of connection
- Add auth provider to prompt user password

## 3.0.1

- Hack fix for the log flood caused when a bled112 dongle gets disconnected

## 3.0.0

- Remove VirtualInterface and replace with an initial implementation of `BLED112DeviceServer`.
  There is still more work to do on the device server to make it production quality but all
  basic functionality works currently.

- Adds mechanism to automatically find the first available BLED112 dongle on a computer so
  that you don't have to hardcode dongle paths if you have multiple `iotile` processes
  running.

## 2.0.4

- Implement proper dependency major version limits.

## 2.0.3

- Remove missed builtins/__future__ calls

## 2.0.2

- Remove past/future/monotonic, pylint cleanup

## 2.0.1

- Ctrl+C breaks if you accidentally double book the bled112 dongle fix(#657)
- Drop python2 support

## 1.8.0

- Update virtual interface for compatibility with new iotile-core version that
  adds callbacks when reports and traced data are actually sent.  Since the
  BLED112 virtual interface snoops on \_queue_reports, it needs to be updated
  to understand the new format of what the arguments to that method mean.

- Refactor broadcast and advertisement packet decoding to better support
  v2 advertisement packets.

## 1.7.4

- Add support for advertising packets version 2.
- Improve behavior of scan to handle empty payloads

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
