## IOTile Transport Native BLE

The IOTile Transport Native BLE plugin allows to connect to use any Bluetooth Low Energy controller
to interact with IOTile devices.
It contains a NativeBLEDeviceAdapter, a NativeBLEVirtualInterface and some tools needed
to make the whole thing work.

To have a cross-platform way to interact with Bluetooth controller, we use [baBLE](https://github.com/iotile/baBLE),
allowing use to send and receive HCI packets, without worrying about the OS (currently only working on Linux).

### Linux requirements

To use **baBLE** without using `sudo`, we need to set its capabilities. To do so, simply run this command after the
transport plugin installation:
```bash
$ bable --set-cap
```
