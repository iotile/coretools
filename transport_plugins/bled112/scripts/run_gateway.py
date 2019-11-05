"""
Runs gateway instance and yappi in order to profile it,
also opens HWManager websocket to the gateway
"""

import time
import logging
import argparse
import multiprocessing
import yappi
from iotile.core.hw import HardwareManager
from iotile.core.utilities import BackgroundEventLoop
from iotile_transport_bled112.utilities import open_bled112
from iotilegateway.gateway import IOTileGateway

logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

gateway_config = {
    "adapters": [
        {
            "name": "bled112",
            "port": "/dev/pts/4"
        }
    ],
    "servers": [
        {
            "name": "websockets",
            "args":
            {
                "port": 5120
            }
        }
    ]
}

def clean_port(port):
    ser = open_bled112(port, logging.getLogger(__name__))
    while ser.in_waiting:
        ser.read()

def open_ws(gateway_event):
    gateway_event.wait()
    gateway_event.clear()

    hw = HardwareManager(port="ws:127.0.0.1:5120/iotile/v1")
    hw.enable_broadcasting()

    gateway_event.wait()
    hw.close()


def profile_gateway(port_node, gateway_event, file_name="log.txt", time_to_profile=300):
    gateway_config["adapters"][0]["port"] = port_node

    loop = BackgroundEventLoop()
    loop.start()

    yappi.start()

    gateway = IOTileGateway(gateway_config, loop)
    loop.run_coroutine(gateway.start())

    gateway_event.set()

    try:
        time.sleep(time_to_profile)
    except KeyboardInterrupt:
        pass

    with open(file_name, "w") as log_file:
        yappi.get_func_stats().print_all(out=log_file, columns= {0:("name",140), 1:("ncall", 10),
                    2:("tsub", 8), 3: ("ttot", 8), 4:("tavg",8)})

    loop.run_coroutine(gateway.stop())
    loop.stop()

    gateway_event.set()

if __name__ == '__main__':
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--time-to-profile", type=int, required=True)
    argparser.add_argument("--log-file", required=True)
    argparser.add_argument("--port", help="/dev/pts/X", required=True)
    argparser.add_argument("--connect-ws", default=False, action='store_true')
    args = argparser.parse_args()

    clean_port(args.port)

    gateway_event = multiprocessing.Event()

    hw_process = None
    if args.connect_ws:
        hw_process = multiprocessing.Process(target=open_ws, args=(gateway_event,))
        hw_process.start()

    profile_gateway(args.port, gateway_event, args.log_file, args.time_to_profile)

    if hw_process:
        hw_process.join()
