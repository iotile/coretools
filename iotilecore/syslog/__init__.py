# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#syslog package

"""
A package for interfacing with the momo hardware syslog.

Methods and objects for dealing with the persistent system log 
present on MoMo controller boards including parsing the log
and preparing log statement definitions for interpreting the
log.
"""

_name_ = "SystemLog"

#Outside accessible API for this package
from descriptor import LogDefinitionMap
from logentry import RawLogEntry
from syslog import SystemLog