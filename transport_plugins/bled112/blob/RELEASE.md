# How to make a BLED112

Make sure you have a Silicon Labs BLED112 dongle, which can be purchased [here](https://www.digikey.com/products/en/rf-if-and-rfid/rf-receiver-transmitter-and-transceiver-finished-units/873?k=bled112).

Download the Bluegiga Bluetooth SDK at this [link](https://www.silabs.com/products/development-tools/software/bluegiga-bluetooth-smart-software-stack). Make sure you do the full installation that includes the BLE SW Update Tool.

Plug in the bled112 dongle you wish to flash firmware to.

Run the BLE GUI tool. In the dropdown menu at the drop, select the device with the correct COM port that corresponds the dongle you wish to update firmware.

Go into Commands->DFU, or press Alt+D to open the Device Firmware Upgrade tool. 'Browse' and select the hex file bled112-v1-6-0-virtual.hex that is in this blob folder, click on 'Upload'. The messages in the text box should say 'Finished' at the end of the process.