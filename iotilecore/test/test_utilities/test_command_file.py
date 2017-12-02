"""Tests of the CommandFile class."""

from iotile.core.utilities.command_file import CommandFile, Command


def test_encoding_idempotency():
    """Make sure encode and decode work."""

    cmd = Command("hello", [1, 'arg1', ' this is, a thing'])

    enc = CommandFile.encode(cmd)
    assert enc == u'hello {1,arg1,hex:20746869732069732c2061207468696e67}'

    dec = CommandFile.decode(enc)
    assert dec == Command("hello", ['1', 'arg1', ' this is, a thing'])


def test_dump_load():
    """Make sure we can dump and load CommandFiles."""

    cmd1 = Command("hello", ['1', 'arg1', ' this is, a thing'])
    cmd2 = Command("cmd2", [])

    cmdfile = CommandFile("TestFormat", "1.0", [cmd1, cmd2])

    out = cmdfile.dump()

    cmdfile2 = CommandFile.FromString(out)

    assert cmdfile2.commands == cmdfile.commands
    assert cmdfile2.version == cmdfile.version
    assert cmdfile2.filetype == cmdfile.filetype
