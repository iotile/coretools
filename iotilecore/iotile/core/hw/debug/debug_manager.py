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
    def flash(self, in_path, file_format=None):
        """Flash a new firmware image to the attached chip.

        This flashing takes place over a debug interface and does not require
        a working bootloader.  In particular, this routien is suitable for
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
