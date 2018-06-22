# IOTile Transport Jlink

## Installation

If you wish to use the FTDI chip to multiplex the jlink, you will need to install [libftdi](https://www.intra2net.com/en/developer/libftdi/), an open source library that pylibftdi uses to communicate with FTDI chips to set multiplexer channels.

pylibftdi gives pretty good instructions on how to install libftdi for your system in this [link]https://pylibftdi.readthedocs.io/en/0.15.0/installation.html. 

For Windows, it's not as clear, but I found [this page](https://stackoverflow.com/questions/32463628/pylibftdi-missing-libftdi-libusb-on-windows-install) to be instructive on how to setup libftdi.