"""Command line script to load and run a sensor graph."""

import sys
import argparse
from builtins import str

def build_args():
    """Create command line argument parser."""

    parser = argparse.ArgumentParser(description=u'Load and run a sensor graph, either in a simulator or on a physical device.')
    parser.add_argument(u'sensor_graph', type=str, help=u"The sensor graph file to load and run.")
    return parser


def main():
    parser = build_args()
    args = parser.parse_args()

    print(args.sensor_graph)
