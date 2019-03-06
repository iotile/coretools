import pytest
import subprocess


class MockSubprocess:
    def __init__(self):
        """Constructor."""

        self.commands = {}

    def mock_command(self, cmd_string, exit_code=0, stdout=None, stderr=None):
        """Mock the command given by cmd_string to return a fixed response.

        Args:
            cmd_string (string): The command that should be mocked including arguments,
                must match exactly.
            exit_code (int): The exit code that should be returned
            stdout (string): The string that should be returned on stdout
            stderr (string): The string that should be returned on stderr
        """

        if stdout is None:
            stdout = ""

        if stderr is None:
            stderr = ""

        self.commands[cmd_string] = {
            'exit_code': exit_code,
            'stdout': stdout,
            'stderr': stderr
        }

    def check_output(self, args, stdin=None, stdout=None, stderr=None, shell=False):
        """Mock check_output call."""

        cmd_str = " ".join(args)
        if cmd_str not in self.commands:
            raise RuntimeError("Could not find mock command by name: %s" % cmd_str)

        cmd = self.commands[cmd_str]

        if stdout is not None:
            stdout.write(cmd['stdout'])

        if stderr is not None:
            stderr.write(cmd['stderr'])

        if cmd['exit_code'] != 0:
            raise subprocess.CalledProcessError(cmd['exit_code'], cmd_str, output=cmd['stdout'])

        return cmd['stdout']

    def check_call(self, args, stdin=None, stdout=None, stderr=None, shell=False):
        """Mock check_call call."""

        cmd_str = " ".join(args)
        if cmd_str not in self.commands:
            raise RuntimeError("Could not find mock command by name: %s" % cmd_str)

        cmd = self.commands[cmd_str]

        if stdout is not None:
            stdout.write(cmd['stdout'])

        if stderr is not None:
            stderr.write(cmd['stderr'])

        if cmd['exit_code'] != 0:
            raise subprocess.CalledProcessError(cmd['exit_code'], cmd_str, output=cmd['stdout'])

        return 0


@pytest.fixture
def mock_subprocess(monkeypatch):
    """Mock check_output, check_call from subprocess with data read from file or literal."""

    mock = MockSubprocess()

    monkeypatch.setattr(subprocess, 'check_output', mock.check_output)
    monkeypatch.setattr(subprocess, 'check_call', mock.check_call)
    return mock
