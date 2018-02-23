"""QEMU based cortex M emulator.

This script allows you to load and run semihosted applications
on a qemu based emulator.
"""

from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str
import sys
import argparse
from iotile.core.exceptions import ArgumentError, IOTileException
import subprocess


DESCRIPTION = \
"""IOTile application emulator.

This program can load and run iotile applications on a modified
qemu emulator
"""


def build_parser():
    """Create command line argument parser."""

    parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('firmware_image', nargs="?", help="The firmware image that you wish to load into the emulator")
    parser.add_argument('--gdb', '-g', type=int, help="Start a GDB server on the given port and wait for a connection")
    return parser


def main(raw_args=None):
    """Run the iotile-emulate script.

    Args:
        raw_args (list): Optional list of commmand line arguments.  If not
            passed these are pulled from sys.argv.
    """

    if raw_args is None:
        raw_args = sys.argv[1:]

    parser = build_parser()
    args = parser.parse_args(raw_args)

    if args.firmware_image is None and args.gdb is None:
        print("You must specify either a firmware image or attach a debugger with --gdb <PORT>")
        return 1

    test_args = ['qemu-system-gnuarmeclipse', '-verbose', '-verbose', '-board', 'STM32F0-Discovery', '-nographic', '-monitor', 'null', '-serial', 'null', '--semihosting-config', 'enable=on,target=native', '-d', 'unimp,guest_errors']

    if args.firmware_image:
        test_args += [ '-image', args.firmware_image]

    if args.gdb:
        test_args += ['--gdb', 'tcp::%d' % args.gdb]

    proc = subprocess.Popen(test_args, stdout=sys.stdout, stderr=sys.stderr)

    try:
        proc.communicate()
    except KeyboardInterrupt:
        proc.terminate()

    return 0
