.. IOTile CoreTools documentation master file, created by
   sphinx-quickstart on Sun Jan 15 09:29:56 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to IOTile
=================

IOTile is a device-to-cloud framework for building cloud connected hardware 
devices.  The goal of IOTile is to make it easy to build and deploy custom
Internet-connected devices, all the way from the low-level hardware and firmware
up through secure connectivity and data storage in the cloud.

**CoreTools** provides an extensible python based infrastructure for creating
and interacting with IOTile Devices.  


Key Concepts
------------

CoreTools is centered around creating and using IOTile Devices, which are 
typically hardware devices (i.e. actual, physical IOT sensors or actuators) but 
can also be virtual agents running on normal computer.

IOTile Devices are usually very small, highly customized things.  

For example, an IOTile Device might be a tiny temperature sensor beacon that 
just broadcasts the current temperature and runs for 10 years on a button cell 
battery.  

There are three main concepts that unify all IOTile Devices:

1. IOTile Devices respond to external commands.  CoreTools calls these commands
   Remote Procedure Calls or RPCs.  RPCs form the heart of how IOTile Devices 
   are controlled and how they work internally as well.

2. IOTile Devices send data to the cloud as timestamped Readings that are 
   packaged into Reports.  Reports can be signed and marked with unique 
   identifiers to make sure they are securely received by the cloud even when 
   transmitted over unreliable or untrusted communications channels.

3. IOTile Devices are built from reusable circuit designs called Tiles.  Tiles
   are the heart of what makes an IOTile Device easier to build and easier to
   use than normal embedded devices.

.. toctree::
   :maxdepth: 2

   introduction
   tutorials
   coretools-internals
   extending-coretools
   typedargs-reference
   building-devices



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

