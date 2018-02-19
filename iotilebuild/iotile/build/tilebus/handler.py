# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.


class TBHandler(object):
    """A representaion of a handler function with type info.

    Args:
        symbol (str): The name of the symbol associated with this handler.
    """

    def __init__(self, symbol=None):
        self.symbol = symbol
