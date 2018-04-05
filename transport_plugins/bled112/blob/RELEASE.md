# How to make a BLED112 Dongle

- Make sure you have a Silicon Labs BLED112 dongle, which can be purchased [here](https://www.digikey.com/products/en/rf-if-and-rfid/rf-receiver-transmitter-and-transceiver-finished-units/873?k=bled112).

- Download the Bluegiga Bluetooth SDK at this [link](https://www.silabs.com/products/development-tools/software/bluegiga-bluetooth-smart-software-stack). Make sure you do the full installation that includes the BLE SW Update Tool.

- Plug in the bled112 dongle you wish to flash firmware to.

- Run the BLE GUI tool. In the dropdown menu at the drop, select the device with the correct COM port that corresponds the dongle you wish to update firmware. 

- Click on 'Attach'

- Go into Commands->DFU, or press Alt+D to open the Device Firmware Upgrade tool. 

- 'Browse' and select the hex file bled112-v1-6-0-virtual.hex that is in this blob folder.

- Click 'Boot into DFU mode', then 'Upload'. The messages in the text box should say 'Finished' at the end of the process. Close the DFU window.

- If you're flashing multiple BLED112s and you unplugged the flash dongle to plug in a new one, make sure you hit 'Refresh' before selecting the new dongle.