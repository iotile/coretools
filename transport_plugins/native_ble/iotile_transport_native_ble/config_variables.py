"""Canonical list of config variables defined by iotile-transport-native-ble."""


def get_variables():
    prefix = "ble"

    conf_vars = [
        ["active-scan", "bool", "Probe devices during scan for uptime, voltage and broadcast data", "false"]
    ]

    return prefix, conf_vars
