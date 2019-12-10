"""Bluetooth Low Energy support package.

This package contains the basic interfaces that all IOTile compatible
bluetooth drivers must implement as well as generic base classes for common
bluetooth objects like advertisements, peripherals, centrals, etc.

The design is such that a single ``DeviceAdapter`` can be written on top of
any ``AbstractBLECentral`` class and provide access to IOTile devices over
a bluetooth connection.

Past CoreTools implementations have not decoupled the underlying ble hardware
enough from the higher level iotile protocol implemented on top of BLE and
thus not been portable to different ble implementations.  The purpose of the
``iotile-transport-blelib`` package is to provide this basic BLE abstract
layer that decouples anything IOTile related from anything BLE protocol
related.
"""

