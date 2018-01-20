# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

# IOTile Exceptions

from typedargs.exceptions import KeyValueException as IOTileException
from typedargs.exceptions import ArgumentError, ValidationError, ConversionError, NotFoundError, TypeSystemError, InternalError


class TimeoutExpiredError(IOTileException):
    """
    The method timed out, usually indicating that a communication failure
    occurred, either with another process or with a hardware module.
    """

    pass


class DataError(IOTileException):
    """
    The method relied on data pass in by the user and the data was invalid.

    This could be because a file was the wrong type or because a data provider
    returned an unexpected result.  The parameters passed with this exception
    provide more detail on what occurred and where.
    """

    pass

class InternalError(IOTileException):
    """
    The method could not be completed with the user input passed for
    an unexpected reason.  This does not signify a bug in the API
    method code.  More details should be passed in the arguments.
    """

    pass

class APIError(IOTileException):
    """
    An internal API error occured during the execution of the method.
    This should only be returned if the error was unforeseen and not
    caused in any way by user input.  If the problem is that a user
    input is invalid for the API call, ValidationError should be
    thrown instead.

    All instances of APIError being thrown are bugs that should be
    reported and fixed.
    """

    pass

class BuildError(IOTileException):
    """
    There is an error with some part of the build system.  This does not
    mean that there is a compilation error but rather that a required part
    of the build process did not complete successfully.  This exception means
    that something is misconfigured.
    """

    pass


class ExternalError(IOTileException):
    """
    The external environment is not properly configured for the IOTile API command that was called.
    This can be because a required program was not installed or accessible or because
    a required environment variable was not defined.
    """

    pass

class HardwareError(IOTileException):
    """
    There was an issue communicating with or controlling an IOTile hardware module.  This
    exception anchors a range of exceptions that refer to specific kinds of hardware issues.

    By catching this exception, you will catch any sort of hardware failure.  If you are
    interested in specific kinds of hardware errors, you can look for or catch subclasses
    of this exception.
    """

    pass
