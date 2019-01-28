"""Canonical list of config variables defined by iotile-transport-bled112."""

from __future__ import unicode_literals, absolute_import, print_function

def get_variables():
    prefix = "bled112"

    conf_vars = []
    conf_vars.append(["active-scan", "bool", "Probe devices during scan for uptime, voltage and broadcast data", "false"])
    conf_vars.append(["throttle-broadcast", "bool", "Only report changing broadcast values, not all values", "false"])

    return prefix, conf_vars
