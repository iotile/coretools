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