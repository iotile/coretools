"""Debug and recovery routines that can be used from HardwareManager.

These routines typically only function when you are connected to
and IOTile Device using a special debug adapter, however in that
case they allow memory dumping and forced reprogramming, including
initial code bootstrapping.
"""

import os.path
import os
import subprocess
import tempfile
import json
from typedargs.annotate import context, docannotate
from iotile.core.exceptions import ArgumentError, ExternalError
from iotile.core.utilities.console import ProgressBar
from iotile.core.utilities.intelhex import IntelHex


@context("DebugManager")
class DebugManager(object):
    """Low level debug operations for development and recovery.

    Args:
        stream (CMDStream): A CMDStream subclass that supports
            debug operations on which enable_debug() has already
            been called.
    """

    def __init__(self, stream):
        self._stream = stream

    @docannotate
    def dump_ram(self, out_path, pause=False):
        """Dump all RAM to a binary file.

        Args:
            out_path (path): The output path at which to save
                the binary core dump.  This core dump consists
                of the current contents of RAM for the device.
            pause (bool): Optional parameter to halt chip operation
                while performing the core dump.  Defaults to False,
                which could cause rapidly changing RAM values to
                be in an inconsistent state, but it noninvasive and
                will not interrupt any device activity.
        """

        ram_contents = self._stream.debug_command('dump_ram', {'halt': pause})

        with open(out_path, "wb") as outfile:
            outfile.write(ram_contents)

    @docannotate
    def save_snapshot(self, out_path):
        """Save the current state of an emulated device.

        This debug routine is only supported for emulated devices that
        have a concept of taking a snapshot of their internal state.

        For those devices this will produce a snapshot file that can
        be used in a later call to load_snapshot() in order to reload
        the exact same state.

        Args:
            out_path (path): The output path at which to save
                the binary core dump.  This core dump consists
                of the current contents of RAM for the device.
        """

        internal_state = self.dump_snapshot()

        with open(out_path, "w") as outfile:
            json.dump(internal_state, outfile, indent=4)

    @docannotate
    def load_snapshot(self, in_path):
        """Load the current state of an emulated device.

        This debug routine is only supported for emulated devices that
        have a concept of restoring a snapshot of their internal state.

        For those devices this method takes a path to a previously produced
        snapshot file from a call to save_snapshot() and will load that
        snapshot into the currently emulated device.

        Args:
            in_path (path): The output path at which to save
                the binary core dump.  This core dump consists
                of the current contents of RAM for the device.
        """

        with open(in_path, "r") as infile:
            internal_state = json.load(infile)

        self.restore_snapshot(internal_state)

    def dump_snapshot(self):
        """Get the current state of the emulated device.

        This debug routine is only supported for emulated devices that
        have a concept of taking a snapshot of their internal state.

        For those devices this will return a snapshot dictionary with
        the entire internal state of the device.

        Returns:
            dict: The internal snapshot of the device's current state.
        """

        return self._stream.debug_command('dump_state')

    def restore_snapshot(self, snapshot):
        """Restore a previous state snapshot from an emulated device.

        Args:
            snapshot (dict): A snapshot of the internal state of this
                device previously obtained by calling dump_snapshot()
        """

        self._stream.debug_command('restore_state', {'snapshot': snapshot})

    @docannotate
    def open_scenario(self, scenario_path):
        """Load a test scenario from a file into an emulated device.

        This debug routine is only supported for emulated devices and will
        cause the connected device to load one of its preconfigured test
        scenarios.  If the scenario has arguments, the args dict
        may be passed to configure it.

        Args:
            scenario_path (str): The path to a file containing the test
                scenario details.
        """

        with open(scenario_path, "r") as infile:
            scenario = json.load(infile)

        self.load_scenario(scenario)

    def load_scenario(self, scenario_data):
        """Load the given test secnario onto an emulated device.

        This debug routine is only supported for emulated devices and will
        cause the connected device to load one of its preconfigured test
        scenarios.  If the scenario has arguments, the args dict
        may be passed to configure it.

        Args:
            scenario_data (list or dict): Either a dict describing the scenario
                to be loaded or a list of such dicts that will all be loaded.
        """

        self._stream.debug_command('load_scenario', {'scenario': scenario_data})

    @docannotate
    def track_changes(self, enabled=True):
        """Start or stop tracking all internal state changes made to an emulated device.

        This debug routine is only supported for emulated devices and will
        causes the device to create an internal log of all state changes.

        This log can be dumped to a file by calling save_change(output_path).

        Args:
            enabled (bool): Whether we should enable (default) or disable tracking
                changes.
        """

        self._stream.debug_command('track_changes', {'enabled': enabled})

    @docannotate
    def save_changes(self, out_path):
        """Save all tracked changes made to an emulated device.

        This debug routine is only supported for emulated devices and will
        causes the device to save all internal state changes since track_changes
        was called.

        Args:
            out_path (str): The output path where the change log should be saved.
        """

        self._stream.debug_command('dump_changes', {'path': out_path})

    @docannotate
    def flash(self, in_path, file_format=None):
        """Flash a new firmware image to the attached chip.

        This flashing takes place over a debug interface and does not require
        a working bootloader.  In particular, this routine is suitable for
        initial board bring-up of a blank MCU.

        If an explicit format is not passed the following rules are used to
        infer the format based on its file extension.

        elf: ELF file
        hex: intel hex file
        bin: raw binary file assumed to start at address 0

        Args:
            in_path (path): The path to the input firmware image that we wish
                to flash.
            file_format (str): Optional explicit format to use to parse the
                input file.  If this is None, the format is automatically
                inferred from the file suffix.  If given explicitly, you
                should pass 'elf', 'hex' or 'bin'.
        """

        format_map = {
            "elf": self._process_elf,
            "hex": self._process_hex,
            "bin": None
        }

        if file_format is None:
            _root, ext = os.path.splitext(in_path)
            if len(ext) > 0:
                file_format = ext[1:]

        format_handler = format_map.get(file_format)
        if format_handler is None:
            raise ArgumentError("Unknown file format or file extension", file_format=file_format, known_formats=[x for x in format_map if format_map[x] is not None])

        base_addresses, section_data = format_handler(in_path)
        for base_address, data in zip(base_addresses, section_data):
            args = {
                'base_address': base_address,
                'data': data
            }

            progress = ProgressBar("Programming Flash")

            def _progress_callback(finished, total):
                progress.count = total
                progress.progress(finished)

            try:
                progress.start()
                self._stream.debug_command('program_flash', args, _progress_callback)
            finally:
                progress.end()

    @classmethod
    def _process_hex(cls, in_path):
        """This function returns a list of base addresses and a list of the binary data
        for each segment.
        """
        ihex           = IntelHex(in_path)
        segments       = ihex.segments()
        segments_start = [segment[0] for segment in segments]
        segments_data  = [ihex.tobinarray(start=segment[0], end=segment[1]-1) for segment in segments]

        return segments_start, segments_data

    @classmethod
    def _process_elf(cls, in_path):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.close()

        try:
            err = subprocess.call(['arm-none-eabi-objcopy', '-O', 'ihex', in_path, tmp.name])
            if err != 0:
                raise ExternalError("Cannot convert elf to binary file", error_code=err,
                                    suggestion="Make sure arm-none-eabi-gcc is installed and in your PATH")

            return cls._process_hex(tmp.name)
        finally:
            if os.path.isfile(tmp.name):
                os.remove(tmp.name)
