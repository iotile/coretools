"""All known and accepted messages that can be sent over WebSockets."""

from iotile.core.utilities.schema_verify import BooleanVerifier, BytesVerifier, DictionaryVerifier, Verifier, \
    EnumVerifier, FloatVerifier, IntVerifier, ListVerifier, LiteralVerifier, OptionsVerifier, StringVerifier

# ------------------------- COMMANDS ------------------------- #

BasicCommand = DictionaryVerifier()
BasicCommand.add_required('type', LiteralVerifier('command'))
BasicCommand.add_required('no_response', BooleanVerifier())

OpenInterfaceCommand = BasicCommand.clone()
OpenInterfaceCommand.add_required('operation', LiteralVerifier('open_interface'))
OpenInterfaceCommand.add_required('interface', EnumVerifier(['rpc', 'streaming', 'tracing', 'script']))

CloseInterfaceCommand = BasicCommand.clone()
CloseInterfaceCommand.add_required('operation', LiteralVerifier('close_interface'))
CloseInterfaceCommand.add_required('interface', EnumVerifier(['rpc', 'streaming', 'tracing', 'script']))

ConnectCommand = BasicCommand.clone()
ConnectCommand.add_required('operation', LiteralVerifier('connect'))

ScriptCommand = BasicCommand.clone()
ScriptCommand.add_required('operation', LiteralVerifier('send_script'))
ScriptCommand.add_required('connection_id', IntVerifier())
ScriptCommand.add_required('fragment_count', IntVerifier())
ScriptCommand.add_required('fragment_index', IntVerifier())
ScriptCommand.add_required('script', Verifier())

DisconnectCommand = BasicCommand.clone()
DisconnectCommand.add_required('operation', LiteralVerifier('disconnect'))

RPCCommand = BasicCommand.clone()
RPCCommand.add_required('operation', LiteralVerifier('send_rpc'))
RPCCommand.add_required('address', IntVerifier())
RPCCommand.add_required('rpc_id', IntVerifier())
RPCCommand.add_required('timeout', FloatVerifier())
RPCCommand.add_required('payload', Verifier())

ProbeCommand = BasicCommand.clone()
ProbeCommand.add_required('operation', LiteralVerifier('probe'))

# ------------------------- RESPONSES ------------------------- #

# All generic responses that we support
BasicResponse = DictionaryVerifier()
BasicResponse.add_required('type', LiteralVerifier('response'))

SuccessfulCommandResponse = BasicResponse.clone()
SuccessfulCommandResponse.add_required('success', LiteralVerifier(True))
SuccessfulCommandResponse.add_optional('payload', Verifier())

FailedCommandResponse = BasicResponse.clone()
FailedCommandResponse.add_required('success', LiteralVerifier(False))
FailedCommandResponse.add_required('failure_reason', StringVerifier())

# Possible Responses to a Connect Command
ConnectPayload = DictionaryVerifier()
ConnectPayload.add_required('connection_id', IntVerifier())

SuccessfulConnectionResponse = SuccessfulCommandResponse.clone()
SuccessfulConnectionResponse.add_required('payload', ConnectPayload)

ConnectionResponse = OptionsVerifier(SuccessfulConnectionResponse, FailedCommandResponse)

# Possible Responses to a Disconnect Command
DisconnectionResponse = OptionsVerifier(SuccessfulCommandResponse, FailedCommandResponse)

# Possible Responses to a Probe Command
ProbePayload = DictionaryVerifier()
ProbePayload.add_required('devices', ListVerifier(Verifier()))

SuccessfulProbeResponse = SuccessfulCommandResponse.clone()
SuccessfulProbeResponse.add_required('payload', ProbePayload)

ProbeResponse = OptionsVerifier(SuccessfulProbeResponse, FailedCommandResponse)

# Possible Responses to Open Interface Command
OpenInterfaceResponse = OptionsVerifier(SuccessfulCommandResponse, FailedCommandResponse)

# Possible Responses to an RPC Command
RPCPayload = DictionaryVerifier()
RPCPayload.add_required('return_value', BytesVerifier())
RPCPayload.add_required('status', IntVerifier())

SuccessfulRPCResponse = SuccessfulCommandResponse.clone()
SuccessfulRPCResponse.add_required('payload', RPCPayload)

RPCResponse = OptionsVerifier(SuccessfulRPCResponse, FailedCommandResponse)

# Possible Responses to the Send Script Command
ScriptResponse = OptionsVerifier(SuccessfulCommandResponse, FailedCommandResponse)

# ------------------------- NOTIFICATIONS ------------------------- #

BasicNotification = DictionaryVerifier()
BasicNotification.add_required('type', LiteralVerifier('notification'))
BasicNotification.add_required('payload', Verifier())

ReportNotification = BasicNotification.clone()
ReportNotification.add_required('operation', LiteralVerifier('report'))

TraceNotification = BasicNotification.clone()
TraceNotification.add_required('operation', LiteralVerifier('trace'))


ProgressPayload = DictionaryVerifier()
ProgressPayload.add_required('connection_id', IntVerifier())
ProgressPayload.add_required('done_count', IntVerifier())
ProgressPayload.add_required('total_count', IntVerifier())

ProgressNotification = BasicNotification.clone()
ProgressNotification.add_required('operation', LiteralVerifier('send_script'))
ProgressNotification.add_required('payload', ProgressPayload)
