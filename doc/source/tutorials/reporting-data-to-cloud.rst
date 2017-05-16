Sending Data to the Cloud
-------------------------

All data from IOTile devices comes in the form of **Reports**.  As the name
suggests, a Report just contains a list of data that the IOTile Device wants
to report to the cloud.  This data is packed into a specific structure for 
transportation to the cloud and then unpacked and inspected to make sure it
arrived correctly and originated from the IOTile Device that it claimed to
come from.

In this tutorial, we're going to build our own reports in Python to get a
feel for how the process works and the various classes involved.

At the end we'll talk about how you could upload a report to the cloud on
behalf of a device.

Goals
#####

1. Understand how IOTile devices report data and how they package it into
   reports for transmission.

2. Introduce the classes in `iotile-core` that represent data from IOTile
   devices and their API. 

3. Understand the distinction between realtime data and signed *Robust Reports*.

4. Introduce the `iotile-ext-cloud` package that allows you to upload reports
   to iotile.cloud.

Background
##########

Before talking about how CoreTools handles data from IOTile Devices, we need to
cover how IOTile devices generate data in the first place.  

IOTile Devices are designed to produce timeseries of discrete data points.
Think of a soil moisture sensor programmed to record the water content in the
soil every 10 minutes.  It produces a series of discrete soil moisture readings
(i.e. single numbers) every 10 minutes.

Now think of a more complicated IOTile Device that measures soil moisture
every 10 minutes but also measures the temperature of the air every hour and
wants to report both of those numbers.  Clearly, there needs to be a way to
distinguish these two data streams so that users know which numbers are
temperatures and which are moisture values.