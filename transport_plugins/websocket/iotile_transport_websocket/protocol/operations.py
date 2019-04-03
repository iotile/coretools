"""List of defined commands and events."""

# Commands
CONNECT = 'connect'
CLOSE_INTERFACE = 'close_interface'
OPEN_INTERFACE = 'open_interface'
PROBE = 'probe'
SEND_RPC = 'send_rpc'
SEND_SCRIPT = 'send_script'
DEBUG = 'debug_command'
DISCONNECT = 'disconnect'

COMMANDS = frozenset([CONNECT, CLOSE_INTERFACE, OPEN_INTERFACE, PROBE, SEND_RPC,
                      SEND_SCRIPT, DISCONNECT, DEBUG])

# Events
NOTIFY_DEVICE_FOUND = 'device_found'
NOTIFY_PROGRESS = 'progress'
NOTIFY_REPORT = 'report'
NOTIFY_BROADCAST = 'broadcast'
NOTIFY_TRACE = 'trace'
NOTIFY_DISCONNECT = 'unexpected_disconnect'

EVENTS = frozenset([NOTIFY_DEVICE_FOUND, NOTIFY_PROGRESS, NOTIFY_REPORT,
                    NOTIFY_BROADCAST, NOTIFY_TRACE, NOTIFY_DISCONNECT])
