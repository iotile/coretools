"""
Script to run mock bled112 devices that can emulate advertising traffic from multiple clients
"""

import argparse
import time
import signal
import sys
import logging
import serial
from iotile_transport_bled112.async_packet import AsyncPacketBuffer
from iotile_transport_bled112.hardware.emulator.mock_adv_bled112 import MockAdvertisingBLED112

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
HEADER_LENGTH = 4

def packet_length(header):
    """
    Find the BGAPI packet length given its header
    """

    highbits = header[0] & 0b11
    lowbits = header[1]

    return (highbits << 8) | lowbits

def loop(bled112, stream, packets_generator):
    if stream.has_packet():
        data = stream.read_packet()
        response = bled112.generate_response(data)
        stream.write(response)

    if bled112.scanning:
        current_time = time.time()

        data = next(packets_generator)
        stream.write(data)

        elapsed_time = time.time() - current_time
        if elapsed_time < 1:
            time.sleep(1 - elapsed_time)

        logging.info("Sent {} packets in {} seconds".format(len(data) // 92, elapsed_time))


def run_observer(serial_port, packets_per_second, unique_devices, update_probability):
    pts = serial.Serial(serial_port, timeout=1)
    packet_buffer = AsyncPacketBuffer(pts, 4, packet_length)

    bled112 = MockAdvertisingBLED112(3)
    adv_packets_generator = bled112.generate_multiple_adv_packets(
        packets_per_second, unique_devices, update_probability)

    try:
        while True:
            loop(bled112, packet_buffer, adv_packets_generator)
    except KeyboardInterrupt:
        pass

    packet_buffer.stop()


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--max-advertisements-per-second", type=int, required=True)
    argparser.add_argument("--port", help="/dev/pts/X", required=True)
    argparser.add_argument("--unique-devices", type=int, default=20,
        help="number of devices to be emulated")
    argparser.add_argument("--stream-value-update-probability", type=int, default=100,
        help="probability that next second stream value will change",
        choices=range(0, 101))
    args = argparser.parse_args()

    run_observer(args.port,
        args.max_advertisements_per_second,
        args.unique_devices,
        args.stream_value_update_probability)

if __name__ == '__main__':
    main()
