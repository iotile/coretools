# How to make a BLED112 Dongle

- Make sure you have a Silicon Labs BLED112 dongle, which can be purchased [here](https://www.digikey.com/products/en/rf-if-and-rfid/rf-receiver-transmitter-and-transceiver-finished-units/873?k=bled112).


## For Linux (requires sudo access):
### This uses the .raw file!
- Install the dfu-util program 
  
  - `apt install dfu-util`

- Unplug all bled112 dongles that you do not intend to flash. 

- Plug in as many bled112 dongles as you would like to flash at once. The script will flash all dongles and can handle any amount

- Run `sudo python3 flash_bled112.py`
  - The script defaults to using the file "bled112-v1-6-0-virtual.raw"
  - You may supply the path to a different file if needed.

- Once the script completes, replace the flashed dongles with the next ones and continue

## For Windows:
### This uses the .hex file!
- Download the Bluegiga Bluetooth SDK at this [link](https://www.silabs.com/products/development-tools/software/bluegiga-bluetooth-smart-software-stack). Make sure you do the full installation that includes the BLE SW Update Tool.

- Plug in the bled112 dongle you wish to flash firmware to.

- Run the BLE GUI tool. In the dropdown menu at the drop, select the device with the correct COM port that corresponds the dongle you wish to update firmware. 

- Click on 'Attach'

- Go into Commands->DFU, or press Alt+D to open the Device Firmware Upgrade tool. 

- 'Browse' and select the hex file bled112-v1-6-0-virtual.hex that is in this blob folder.

- Click 'Boot into DFU mode', then 'Upload'. The messages in the text box should say 'Finished' at the end of the process. Close the DFU window.

- If you're flashing multiple BLED112s and you unplugged the flash dongle to plug in a new one, make sure you hit 'Refresh' before selecting the new dongle.


## To create the .raw file from a .hex file:

- According to https://www.silabs.com/documents/login/reference-manuals/Bluetooth_Smart_Software-BLE-1.7-API-RM.PDF page 207:
    ```
Use data
contained in the firmware image .hex file starting from byte offset 0x1000: everything before this offset is
bootloader data which cannot be written using DFU; also, the last 2kB are skipped because they contain
the hardware page and other configuration data that cannot be changed over DFU.
```
- Modify the hex file:(See https://en.wikipedia.org/wiki/Intel_HEX for file format)

  - Do not touch the first line. It contains the Extended Linear Address record

  - Starting after the first line, delete every line up to but not including the one that starts with ":101000". This line is byte offset 0x1000.

  - Go to the end of the file. Do not touch the last line, which contains the end of file info

   - Delete the 128 lines previous to the last line. Each line contains 16 bytes, and 2kB (2048) / 16 is 128.
 
- Convert the file to raw:

  - Using the Linux dfu-tool utility: (the dfu-util utility doesn't include file conversion)

    - `dfu-tool convert raw <file>.hex <file>.raw`

