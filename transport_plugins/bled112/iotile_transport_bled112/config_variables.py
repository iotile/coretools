"""Canonical list of config variables defined by iotile-transport-bled112."""


def get_variables():
    prefix = "bled112"

    conf_vars = []
    conf_vars.append(["active-scan", "bool", "Probe devices during scan for uptime, voltage and broadcast data", "false"])
    conf_vars.append(["throttle-broadcast", "bool", "Only report changing broadcast values, not all values", "false"])
    conf_vars.append(["throttle-scan", "bool", "Only report device_seen once in a timeout", "false"])
    conf_vars.append(["throttle-timeout", "int", "device_seen and report events timeout in seconds", 30])

    return prefix, conf_vars
