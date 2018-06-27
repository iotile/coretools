"""A parser/generator for a list of commands with arguments.

All commands are single words with arguments as follows:

command_name {arg1, arg2, arg3}

If the contents of argN contains a , or begins or ends with whitespace
it is utf-8 encoded and stored as hex of the form hex:xxxxx
"""

from __future__ import unicode_literals
from builtins import str
from collections import namedtuple
from binascii import hexlify, unhexlify
from iotile.core.exceptions import DataError


Command = namedtuple("Command", ["name", "args"])

class CommandFile(object):
    """A versioned and typed list of commands.

    Args:
        filetype (str): The name of the file type
        version (str): An X.Y.Z version number
        commands (list): A list of Command objects used to
            initialize the command file.
    """


    def __init__(self, filetype, version, commands=None):
        if commands is None:
            commands = []

        self.commands = commands
        self.validators = {}
        self.filetype = filetype
        self.version = version

    def add(self, command, *args):
        """Add a command to this command file.

        Args:
            command (str): The command to add
            *args (str): The parameters to call the command with
        """

        cmd = Command(command, args)
        self.commands.append(cmd)

    def save(self, outpath):
        """Save this command file as an ascii file.

        Agrs:
            outpath (str): The output path to save.
        """

        with open(outpath, "w") as outfile:
            outfile.write(self.dump())

    def dump(self):
        """Dump all commands in this object to a string.

        Returns:
            str: An encoded list of commands separated by
                \n characters suitable for saving to a file.
        """

        out = []

        out.append(self.filetype)
        out.append("Format: {}".format(self.version))
        out.append("Type: ASCII")
        out.append("")

        for cmd in self.commands:
            out.append(self.encode(cmd))

        return "\n".join(out) + "\n"

    @classmethod
    def FromString(cls, indata):
        """Load a CommandFile from a string.

        The string should be produced from a previous call to
        encode.

        Args:
            indata (str): The encoded input data.

        Returns:
            CommandFile: The decoded CommandFile object.
        """

        lines = [x.strip() for x in indata.split("\n") if not x.startswith('#') and not x.strip() == ""]

        if len(lines) < 3:
            raise DataError("Invalid CommandFile string that did not contain 3 header lines", lines=lines)

        fmt_line, version_line, ascii_line = lines[:3]

        if not version_line.startswith("Format: "):
            raise DataError("Invalid format version that did not start with 'Format: '", line=version_line)

        version = version_line[8:]

        if ascii_line != "Type: ASCII":
            raise DataError("Unknown file type line (expected Type: ASCII)", line=ascii_line)

        cmds = [cls.decode(x) for x in lines[3:]]
        return CommandFile(fmt_line, version, cmds)

    @classmethod
    def FromFile(cls, inpath):
        """Load a CommandFile from a path.

        Args:
            inpath (str): The path to the file to load

        Returns:
            CommandFile: The decoded CommandFile object.
        """

        with open(inpath, "r") as infile:
            indata = infile.read()

        return cls.FromString(indata)

    @classmethod
    def encode(cls, command):
        """Encode a command as an unambiguous string.

        Args:
            command (Command): The command to encode.

        Returns:
            str: The encoded command
        """

        args = []
        for arg in command.args:
            if not isinstance(arg, str):
                arg = str(arg)

            if "," in arg or arg.startswith(" ") or arg.endswith(" ") or arg.startswith("hex:"):
                arg = "hex:{}".format(hexlify(arg.encode('utf-8')).decode('utf-8'))

            args.append(arg)

        argstr = ""

        if len(args) > 0:
            argstr = " {" + ",".join(args) + "}"

        return command.name + argstr

    @classmethod
    def decode(cls, command_str):
        """Decode a string encoded command back into a Command object.

        Args:
            command_str (str): The encoded command string output from a
                previous call to encode.

        Returns:
            Command: The decoded Command object.
        """

        name, _, arg = command_str.partition(" ")

        args = []

        if len(arg) > 0:
            if arg[0] != '{' or arg[-1] != '}':
                raise DataError("Invalid command, argument is not contained in { and }", arg=arg, cmd=name)

            arg = arg[1:-1]
            args = arg.split(",")

        proc = []

        for arg in args:
            if arg.startswith("hex:"):
                arg = unhexlify(arg[4:]).decode('utf-8')

            proc.append(arg)

        return Command(name, proc)
