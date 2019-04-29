"""List of known command and response payloads."""

from iotile.core.utilities.schema_verify import BytesVerifier, DictionaryVerifier, \
    EnumVerifier, FloatVerifier, IntVerifier, StringVerifier, NoneVerifier, Verifier, \
    OptionsVerifier

# Connect Command
ConnectCommand = DictionaryVerifier()
ConnectCommand.add_required('connection_string', StringVerifier())

ConnectResponse = NoneVerifier()

# Disconnect Command
DisconnectCommand = DictionaryVerifier()
DisconnectCommand.add_required('connection_string', StringVerifier())

DisconnectResponse = NoneVerifier()


_InterfaceEnum = EnumVerifier(['rpc', 'streaming', 'tracing', 'script', 'debug'])

# OpenInterface Command

OpenInterfaceCommand = DictionaryVerifier()
OpenInterfaceCommand.add_required('interface', _InterfaceEnum)
OpenInterfaceCommand.add_required('connection_string', StringVerifier())

OpenInterfaceResponse = NoneVerifier()
# CloseInterface Command

CloseInterfaceCommand = DictionaryVerifier()
CloseInterfaceCommand.add_required('interface', _InterfaceEnum)
CloseInterfaceCommand.add_required('connection_string', StringVerifier())

CloseInterfaceResponse = NoneVerifier()

# Probe
ProbeCommand = NoneVerifier()
ProbeResponse = NoneVerifier()

# Send RPC
SendRPCCommand = DictionaryVerifier()
SendRPCCommand.add_required('connection_string', StringVerifier())
SendRPCCommand.add_required('address', IntVerifier())
SendRPCCommand.add_required('rpc_id', IntVerifier())
SendRPCCommand.add_required('timeout', FloatVerifier())
SendRPCCommand.add_required('payload', BytesVerifier(encoding="base64"))

SendRPCResponse = DictionaryVerifier()
SendRPCResponse.add_required('status', IntVerifier())
SendRPCResponse.add_required('payload', BytesVerifier(encoding="base64"))

# Send script
SendScriptCommand = DictionaryVerifier()
SendScriptCommand.add_required('connection_string', StringVerifier())
SendScriptCommand.add_required('fragment_count', IntVerifier())
SendScriptCommand.add_required('fragment_index', IntVerifier())
SendScriptCommand.add_required('script', BytesVerifier(encoding="base64"))

SendScriptResponse = NoneVerifier()

SendDebugCommand = DictionaryVerifier()
SendScriptCommand.add_required('connection_string', StringVerifier())
SendDebugCommand.add_required('command', StringVerifier())
SendDebugCommand.add_required('args', Verifier())

SendDebugResponse = Verifier()
