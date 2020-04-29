"""
Runs gateway instance and yappi in order to profile it,
also opens HWManager websocket to the gateway and start bled112 mock device
"""

import time
import logging
import argparse
import multiprocessing
import subprocess

from run_gateway import profile_gateway, open_ws
from run_mock_observer import run_observer


logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--time-to-profile", type=int, required=True)
    argparser.add_argument("--log-file", required=True)
    argparser.add_argument("--connect-ws", default=False, action='store_true')
    argparser.add_argument("--max-advertisements-per-second", type=int, required=True)
    argparser.add_argument("--unique-devices", type=int, default=20,
        help="number of devices to be emulated(defaults to 0, every new packet is unique")
    argparser.add_argument("--stream-value-update-probability", type=int, default=100,
        help="probability that next second stream value will change",
        choices=range(0, 101))
    argparser.add_argument("--device-adapter", help="[bled112 | async_bled112]", default="bled112")
    args = argparser.parse_args()

    pts1_link = "/tmp/ttyV0"
    pts2_link = "/tmp/ttyV1"
    socat_cmd = "socat -d -d pty,raw,echo=0,link={} pty,raw,echo=0,link={}".format(
        pts1_link, pts2_link)

    socat_process = subprocess.Popen(socat_cmd.split())
    time.sleep(1)

    observer_args = (pts1_link,
                     args.max_advertisements_per_second,
                     args.unique_devices,
                     args.stream_value_update_probability)
    observer_process = multiprocessing.Process(target=run_observer, args=observer_args)
    observer_process.start()

    gateway_event = multiprocessing.Event()

    hw_process = None
    if args.connect_ws:
        hw_process = multiprocessing.Process(target=open_ws, args=(gateway_event,))
        hw_process.start()

    profile_gateway(pts2_link, gateway_event, args.log_file, args.time_to_profile, args.device_adapter)

    if hw_process:
        hw_process.join()

    observer_process.terminate()
    observer_process.join()

    socat_process.terminate()
    socat_process.wait()


if __name__ == '__main__':
    main()
