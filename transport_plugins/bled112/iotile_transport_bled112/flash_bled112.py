import serial
import argparse
import subprocess
import time

from iotile_transport_bled112.bled112 import BLED112Adapter

_BAUD_RATE = 230400

def reset(port):
    # See https://www.silabs.com/documents/login/reference-manuals/Bluetooth_Smart_Software-BLE-1.7-API-RM.PDF
    # Page 188
    packet = bytearray(5)
    packet[0] = 0       #Type Ccommand
    packet[1] = 0x01    #Payload length
    packet[2] = 0x00    #Class: Reset
    packet[3] = 0       #Message ID
    packet[4] = 0x01    # Payload (0x1 for boot to DFU)

    opened_port = serial.Serial(port, _BAUD_RATE, timeout=0.01, rtscts=True, exclusive=True)
    opened_port.write(bytes(packet))
    opened_port.close()

def add_ready_bleds(paths):
    cmd = subprocess.run(["dfu-util", "-l"], stdout=subprocess.PIPE, universal_newlines=True)
    dfu_list = cmd.stdout

    for line in dfu_list.splitlines():
        if "[2458:fffe]" not in line:
            continue
        #print("working with", line)
        pathstart = line.find("path=")
        path = line[pathstart:].split('"')[1]
        #print(path)
        if not [ x for x in paths if x.path == path]:
            paths.append(ready_bled(path))

class ready_bled():
    def __init__(self, path):
        self.path = path
        self.flashed = False

    def flash(self, blob):
        print("flashing", self.path)
        flash_cmd = ["dfu-util", "-R", "-D", blob, "-p", self.path]
        subprocess.run(flash_cmd, check=True)
        self.flashed = True


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("blob")
    args = parser.parse_args()

    bleds = BLED112Adapter.find_bled112_devices()
    print("Flashing", bleds)
    num_bleds_remaining = len(bleds)
    paths = []

    for bled in bleds:
        reset(bled)
        print("Reset", bled)

    add_ready_bleds(paths)
    while num_bleds_remaining > 0:
        time.sleep(0.5)
        add_ready_bleds(paths)
        for bled in [x for x in paths if x.flashed == False]:
            bled.flash(args.blob)
            num_bleds_remaining -= 1
        print("Waiting for", num_bleds_remaining, "bleds to finish resetting")
















    #bledadapter = BLED112Adapter(port = port, passive=True)

    #bledadapter._command_task._reset()
    #bledadapter.stop_sync()
