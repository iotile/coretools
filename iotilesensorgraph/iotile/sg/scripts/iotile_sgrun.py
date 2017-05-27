"""Command line script to load and run a sensor graph."""

import sys
import argparse
from builtins import str
from iotile.sg import SensorGraph, SensorLog, DeviceModel
from iotile.sg.sim import SensorGraphSimulator

def build_args():
    """Create command line argument parser."""

    parser = argparse.ArgumentParser(description=u'Load and run a sensor graph, either in a simulator or on a physical device.')
    parser.add_argument(u'sensor_graph', type=str, help=u"The sensor graph file to load and run.")
    parser.add_argument(u'stop', action=append, type=str, help=u"A stop condition for when the simulation should end.")

    return parser


def main():
    parser = build_args()
    args = parser.parse_args()

    model = DeviceModel()
    log = SensorLog(model=model)
    graph = SensorGraph()


    print(args.sensor_graph)
