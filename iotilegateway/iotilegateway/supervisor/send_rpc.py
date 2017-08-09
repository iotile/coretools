"""A simple command line program for sending an RPC to a service by name."""

import sys
import os
import argparse
import logging
import binascii
import struct
from .status_client import ServiceStatusClient


def _build_parser():
    parser = argparse.ArgumentParser(description="Send a single RPC to a service via the IOTileSupervisor")

    parser.add_argument('-s', '--supervisor', type=str, default="ws://127.0.0.1:9400/services", help="The URL of an IOTileSupervisor server to manage this daemon")
    parser.add_argument('-f', '--arg-format', type=str, help="The python struct.pack format code that should be used to pack rpc arguments")
    parser.add_argument('-r', '--response-format', type=str, help="The python struct.pack format code that should be used to unpack the rpc response")

    parser.add_argument('service_name', type=str, help="The short name of the service that you would like to send the RPC to")
    parser.add_argument('rpc_id', type=lambda x: int(x, 0), help="The RPC id that you would like to call, in [0 and 65535]")
    parser.add_argument('args', nargs=argparse.REMAINDER)

    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument('-q', '--quiet', action='store_true', help="Do not report any status and information")
    verbosity.add_argument('-v', '--verbose', action='count', help="Report extra debug information (pass twice for binary dumps of input records)")

    return parser


def pack_args(fmt, args):
    int_args = [int(x, 0) for x in args]

    packed = struct.pack("<%s" % fmt, *int_args)
    return packed

def main():
    parser = _build_parser()

    args = parser.parse_args()

    verbose = args.verbose >= 1

    log_level = logging.INFO
    if args.quiet:
        log_level = logging.CRITICAL
    elif verbose:
        log_level = logging.DEBUG

    logging.basicConfig(level=log_level, format='[%(asctime)-15s] %(levelname)-6s %(message)s', datefmt='%d/%b/%Y %H:%M:%S')
    logger = logging.getLogger(__name__)

    try:
        client = ServiceStatusClient(args.supervisor)
    except Exception:
        logger.exception("Could not create status client to connect to supervisor")
        return 1

    logger.debug("Sending RPC to service: %s, rpc id: 0x%X", args.service_name, args.rpc_id)

    packed_args = b''

    if len(args.args) > 0 and args.arg_format is not None:
        packed_args = pack_args(args.arg_format, args.args)
    elif len(args.args) > 0:
        print("Invalid arguments specified without a format string")
        return 1

    resp = client.send_rpc(args.service_name, args.rpc_id, packed_args)

    if resp['result'] != 'success':
        print("RPC failed: %s" % resp['result'])
        return 1

    response = resp['response']
    logger.debug("RPC Response: %s", binascii.hexlify(response))

    if args.response_format is not None:
        unpacked = struct.unpack("<%s" % args.response_format, response)
        for i, val in enumerate(unpacked):
            print("Result %d: %s" % (i+1, val))

        return 0

    print("Unprocessed Hex Response: %s" % binascii.hexlify(response))
