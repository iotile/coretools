import serial
import argparse
import subprocess
import time

from iotile_transport_bled112.bled112 import BLED112Adapter

_BAUD_RATE = 230400

_BLED_ID = "[2458:fffe]"

def reset(port):
    # See https://www.silabs.com/documents/login/reference-manuals/Bluetooth_Smart_Software-BLE-1.7-API-RM.PDF
    # Page 188
    packet = bytearray(5)
    packet[0] = 0       #Type Ccommand
    packet[1] = 0x01    #Payload length
    packet[2] = 0x00    #Class: Reset
    packet[3] = 0       #Message ID
    packet[4] = 0x01    #Payload (0x1 for boot to DFU)

    opened_port = serial.Serial(port, _BAUD_RATE, timeout=0.01, rtscts=True, exclusive=True)
    opened_port.write(bytes(packet))
    opened_port.close()

def add_ready_bleds(ready_bleds):
    cmd = subprocess.run(["dfu-util", "-l"], stdout=subprocess.PIPE, universal_newlines=True)
    dfu_list = cmd.stdout

    for line in dfu_list.splitlines():
        if _BLED_ID not in line:
            continue

        # Parse out the path from dfu-util's output. Example output:
        # Found DFU: [2458:fffe] ver=0000, devnum=80, cfg=1, intf=0, path="1-2.2", alt=0, name="DFU", serial="1234"

        pathstart = line.find("path=")
        path = line[pathstart:].split('"')[1]

        # only add it to the list if it's a new path.
        if not [x for x in ready_bleds if x.path == path]:
            ready_bleds.append(ready_bled(path))

class ready_bled():
    def __init__(self, path):
        self.path = path
        self.flashed = False

    def flash(self, blob):
        print("Flashing", self.path)
        flash_cmd = ["dfu-util", "-R", "-D", blob, "-p", self.path]
        subprocess.run(flash_cmd, check=True)
        self.flashed = True


def check_pre_requisites():
    import os
    import shutil

    if os.geteuid() != 0:
        exit("This script must be run as root")

    if not shutil.which("dfu-util"):
        exit("Requires the dfu-util utility")


if __name__ == "__main__":

    check_pre_requisites()

    parser = argparse.ArgumentParser()
    parser.add_argument("blob", nargs='?', default="bled112-v1-6-0-virtual.raw")
    args = parser.parse_args()

    bleds = BLED112Adapter.find_bled112_devices()
    print("Flashing", bleds)
    num_bleds_remaining = len(bleds)
    ready_bleds = []

    for bled in bleds:
        reset(bled)
        print("Reset", bled)

    # Bleds may not all reset at the same speed. So, note the number of bleds that
    # we should be flashing, and keep looking for them until we find and flash
    # all of them.
    while num_bleds_remaining > 0:
        time.sleep(0.5)

        add_ready_bleds(ready_bleds)

        for bled in [x for x in ready_bleds if x.flashed == False]:
            bled.flash(args.blob)
            num_bleds_remaining -= 1
        print("Waiting for", num_bleds_remaining, "bleds to finish resetting")
