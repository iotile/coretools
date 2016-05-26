# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

"""
A package for managing bills of materials and pcb fabrication

Methods and objects for creating and pricing bills of materials
as well as automatically generating gerber files for pcb fabrication.

- The CircuitBoard object provides a way to generate BOMs and production
  files for pcb fabrication from ECAD files
- various BOM pricing and matching engines like OctopartMatcher allow you
  to see how much your BOM would cost in different quantities.
"""

_name_ = "pcb"


#Add in required types that we need 
import types
import iotilecore.utilities.typedargs
iotilecore.utilities.typedargs.type_system.load_type_module(types)

from match_engines import *
from board import CircuitBoard
