from iotile.core.utilities.schema_verify import DictionaryVerifier, Verifier, \
    EnumVerifier, FloatVerifier, IntVerifier, LiteralVerifier, StringVerifier
import operations

Basic = DictionaryVerifier()
Basic.add_required('type', LiteralVerifier('command'))
Basic.add_required('connection_string', StringVerifier())

# Connect
Connect = Basic.clone()
Connect.add_required('operation', LiteralVerifier(operations.CONNECT))

# Close interface
CloseInterface = Basic.clone()
CloseInterface.add_required('operation', LiteralVerifier(operations.CLOSE_INTERFACE))
CloseInterface.add_required('interface', EnumVerifier(['rpc', 'streaming', 'tracing', 'script', 'debug']))

# Disconnect
Disconnect = Basic.clone()
Disconnect.add_required('operation', LiteralVerifier(operations.DISCONNECT))

# Open interface
OpenInterface = Basic.clone()
OpenInterface.add_required('operation', LiteralVerifier(operations.OPEN_INTERFACE))
OpenInterface.add_required('interface', EnumVerifier(['rpc', 'streaming', 'tracing', 'script', 'debug']))

# Scan
Scan = DictionaryVerifier()
Scan.add_required('type', LiteralVerifier('command'))
Scan.add_required('operation', LiteralVerifier(operations.SCAN))

# Send RPC
SendRPC = Basic.clone()
SendRPC.add_required('operation', LiteralVerifier(operations.SEND_RPC))
SendRPC.add_required('address', IntVerifier())
SendRPC.add_required('rpc_id', IntVerifier())
SendRPC.add_required('timeout', FloatVerifier())
SendRPC.add_required('payload', Verifier())

# Send script
SendScript = Basic.clone()
SendScript.add_required('operation', LiteralVerifier(operations.SEND_SCRIPT))
SendScript.add_required('fragment_count', IntVerifier())
SendScript.add_required('fragment_index', IntVerifier())
SendScript.add_required('script', Verifier())
