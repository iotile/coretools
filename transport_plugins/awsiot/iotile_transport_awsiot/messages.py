"""All known and accepted messages that can be sent over AWS IOT."""

from iotile.core.utilities.schema_verify import Verifier, OptionsVerifier, EnumVerifier, ListVerifier, BytesVerifier, IntVerifier, LiteralVerifier, FloatVerifier, DictionaryVerifier, StringVerifier


# All control messages that we support
OpenInterfaceCommand = DictionaryVerifier()  # pylint: disable=C0103
OpenInterfaceCommand.add_required('type', LiteralVerifier('command'))
OpenInterfaceCommand.add_required('operation', LiteralVerifier('open_interface'))
OpenInterfaceCommand.add_required('key', StringVerifier())
OpenInterfaceCommand.add_required('client', StringVerifier())
OpenInterfaceCommand.add_required('interface', EnumVerifier(['rpc', 'streaming', 'tracing', 'script']))

CloseInterfaceCommand = DictionaryVerifier()  # pylint: disable=C0103
CloseInterfaceCommand.add_required('type', LiteralVerifier('command'))
CloseInterfaceCommand.add_required('operation', LiteralVerifier('close_interface'))
CloseInterfaceCommand.add_required('key', StringVerifier())
CloseInterfaceCommand.add_required('client', StringVerifier())
CloseInterfaceCommand.add_required('interface', EnumVerifier(['rpc', 'streaming', 'tracing', 'script']))

ConnectCommand = DictionaryVerifier()  # pylint: disable=C0103
ConnectCommand.add_required('type', LiteralVerifier('command'))
ConnectCommand.add_required('operation', LiteralVerifier('connect'))
ConnectCommand.add_required('key', StringVerifier())
ConnectCommand.add_required('client', StringVerifier())

ScriptCommand = DictionaryVerifier()  # pylint: disable=C0103
ScriptCommand.add_required('type', LiteralVerifier('command'))
ScriptCommand.add_required('operation', LiteralVerifier('send_script'))
ScriptCommand.add_required('fragment_count', IntVerifier())
ScriptCommand.add_required('fragment_index', IntVerifier())
ScriptCommand.add_required('key', StringVerifier())
ScriptCommand.add_required('client', StringVerifier())
ScriptCommand.add_required('script', BytesVerifier(encoding="base64"))

DisconnectCommand = DictionaryVerifier()  # pylint: disable=C0103
DisconnectCommand.add_required('type', LiteralVerifier('command'))
DisconnectCommand.add_required('operation', LiteralVerifier('disconnect'))
DisconnectCommand.add_required('key', StringVerifier())
DisconnectCommand.add_required('client', StringVerifier())

RPCCommand = DictionaryVerifier()  # pylint: disable=C0103
RPCCommand.add_required('type', LiteralVerifier('command'))
RPCCommand.add_required('operation', LiteralVerifier('rpc'))
RPCCommand.add_required('key', StringVerifier())
RPCCommand.add_required('client', StringVerifier())
RPCCommand.add_required('address', IntVerifier())
RPCCommand.add_required('rpc_id', IntVerifier())
RPCCommand.add_required('timeout', FloatVerifier())
RPCCommand.add_required('payload', BytesVerifier(encoding='hex'))

ProbeCommand = DictionaryVerifier()  # pylint: disable=C0103
ProbeCommand.add_required('type', LiteralVerifier('command'))
ProbeCommand.add_required('operation', LiteralVerifier('probe'))
ProbeCommand.add_required('client', StringVerifier())

# All generic responses that we support
SuccessfulCommandResponse = DictionaryVerifier()  # pylint: disable=C0103
SuccessfulCommandResponse.add_required('type', LiteralVerifier('response'))
SuccessfulCommandResponse.add_required('client', StringVerifier())
SuccessfulCommandResponse.add_required('success', LiteralVerifier(True))

FailedCommandResponse = DictionaryVerifier()  # pylint: disable=C0103
FailedCommandResponse.add_required('type', LiteralVerifier('response'))
FailedCommandResponse.add_required('client', StringVerifier())
FailedCommandResponse.add_required('success', LiteralVerifier(False))
FailedCommandResponse.add_required('failure_reason', StringVerifier())

ProbeResponse = DictionaryVerifier()  # pylint: disable=C0103
ProbeResponse.add_required('type', LiteralVerifier('response'))
ProbeResponse.add_required('client', StringVerifier())
ProbeResponse.add_required('success', LiteralVerifier(True))
ProbeResponse.add_required('devices', ListVerifier(Verifier()))

# Possible Responses to a Connect Command
SuccessfulConnectionResponse = DictionaryVerifier()  # pylint: disable=C0103
SuccessfulConnectionResponse.add_required('type', LiteralVerifier('response'))
SuccessfulConnectionResponse.add_required('operation', LiteralVerifier('connect'))
SuccessfulConnectionResponse.add_required('client', StringVerifier())
SuccessfulConnectionResponse.add_required('success', LiteralVerifier(True))

FailedConnectionResponse = DictionaryVerifier()  # pylint: disable=C0103
FailedConnectionResponse.add_required('type', LiteralVerifier('response'))
FailedConnectionResponse.add_required('operation', LiteralVerifier('connect'))
FailedConnectionResponse.add_required('client', StringVerifier())
FailedConnectionResponse.add_required('success', LiteralVerifier(False))
FailedConnectionResponse.add_required('failure_reason', StringVerifier())

ConnectionResponse = OptionsVerifier(SuccessfulConnectionResponse, FailedConnectionResponse)  # pylint: disable=C0103

# Possible Responses to a Disconnect Command
SuccessfulDisconnectionResponse = DictionaryVerifier()  # pylint: disable=C0103
SuccessfulDisconnectionResponse.add_required('type', LiteralVerifier('response'))
SuccessfulDisconnectionResponse.add_required('operation', LiteralVerifier('disconnect'))
SuccessfulDisconnectionResponse.add_required('client', StringVerifier())
SuccessfulDisconnectionResponse.add_required('success', LiteralVerifier(True))

FailedDisconnectionResponse = DictionaryVerifier()  # pylint: disable=C0103
FailedDisconnectionResponse.add_required('type', LiteralVerifier('response'))
FailedDisconnectionResponse.add_required('operation', LiteralVerifier('disconnect'))
FailedDisconnectionResponse.add_required('client', StringVerifier())
FailedDisconnectionResponse.add_required('success', LiteralVerifier(False))
FailedDisconnectionResponse.add_required('failure_reason', StringVerifier())

DisconnectionResponse = OptionsVerifier(SuccessfulDisconnectionResponse, FailedDisconnectionResponse)  # pylint: disable=C0103

# Possible Responses to Open Interface Command
SuccessfulOpenIfaceResponse = DictionaryVerifier()  # pylint: disable=C0103
SuccessfulOpenIfaceResponse.add_required('type', LiteralVerifier('response'))
SuccessfulOpenIfaceResponse.add_required('operation', LiteralVerifier('open_interface'))
SuccessfulOpenIfaceResponse.add_required('client', StringVerifier())
SuccessfulOpenIfaceResponse.add_required('success', LiteralVerifier(True))

FailedOpenIfaceResponse = DictionaryVerifier()  # pylint: disable=C0103
FailedOpenIfaceResponse.add_required('type', LiteralVerifier('response'))
FailedOpenIfaceResponse.add_required('operation', LiteralVerifier('open_interface'))
FailedOpenIfaceResponse.add_required('client', StringVerifier())
FailedOpenIfaceResponse.add_required('success', LiteralVerifier(False))
FailedOpenIfaceResponse.add_required('failure_reason', StringVerifier())

OpenInterfaceResponse = OptionsVerifier(SuccessfulOpenIfaceResponse, FailedOpenIfaceResponse)  # pylint: disable=C0103

# Possible Responses to an RPC Command
SuccessfulRPCResponse = DictionaryVerifier()  # pylint: disable=C0103
SuccessfulRPCResponse.add_required('type', LiteralVerifier('response'))
SuccessfulRPCResponse.add_required('operation', LiteralVerifier('rpc'))
SuccessfulRPCResponse.add_required('client', StringVerifier())
SuccessfulRPCResponse.add_required('success', LiteralVerifier(True))
SuccessfulRPCResponse.add_required('status', IntVerifier())
SuccessfulRPCResponse.add_required('payload', BytesVerifier(encoding='hex'))

FailedRPCResponse = DictionaryVerifier()  # pylint: disable=C0103
FailedRPCResponse.add_required('type', LiteralVerifier('response'))
FailedRPCResponse.add_required('operation', LiteralVerifier('rpc'))
FailedRPCResponse.add_required('client', StringVerifier())
FailedRPCResponse.add_required('success', LiteralVerifier(False))

RPCResponse = OptionsVerifier(SuccessfulRPCResponse, FailedRPCResponse)  # pylint: disable=C0103

# Possible Responses to the Send Script Command
SuccessfulScriptResponse = DictionaryVerifier()  # pylint: disable=C0103
SuccessfulScriptResponse.add_required('type', LiteralVerifier('response'))
SuccessfulScriptResponse.add_required('operation', LiteralVerifier('send_script'))
SuccessfulScriptResponse.add_required('client', StringVerifier())
SuccessfulScriptResponse.add_required('success', LiteralVerifier(True))

FailedScriptResponse = DictionaryVerifier()  # pylint: disable=C0103
FailedScriptResponse.add_required('type', LiteralVerifier('response'))
FailedScriptResponse.add_required('operation', LiteralVerifier('send_script'))
FailedScriptResponse.add_required('client', StringVerifier())
FailedScriptResponse.add_required('success', LiteralVerifier(False))
FailedScriptResponse.add_required('failure_reason', StringVerifier())

ScriptResponse = OptionsVerifier(SuccessfulScriptResponse, FailedScriptResponse)  # pylint: disable=C0103

# Notifications that we support
ReportNotification = DictionaryVerifier()  # pylint: disable=C0103
ReportNotification.add_required('type', LiteralVerifier('notification'))
ReportNotification.add_required('fragment_count', IntVerifier())
ReportNotification.add_required('fragment_index', IntVerifier())
ReportNotification.add_required('operation', LiteralVerifier('report'))
ReportNotification.add_required('received_time', StringVerifier())
ReportNotification.add_required('report', BytesVerifier(encoding='hex'))
ReportNotification.add_required('report_origin', IntVerifier())
ReportNotification.add_required('report_format', IntVerifier())

TracingNotification = DictionaryVerifier()  # pylint: disable=C0103
TracingNotification.add_required('type', LiteralVerifier('notification'))
TracingNotification.add_required('operation', LiteralVerifier('trace'))
TracingNotification.add_required('trace_origin', IntVerifier())
TracingNotification.add_required('trace', BytesVerifier(encoding='hex'))

ProgressNotification = DictionaryVerifier()  # pylint: disable=C0103
ProgressNotification.add_required('type', LiteralVerifier('notification'))
ProgressNotification.add_required('operation', LiteralVerifier('send_script'))
ProgressNotification.add_required('client', StringVerifier())
ProgressNotification.add_required('done_count', IntVerifier())
ProgressNotification.add_required('total_count', IntVerifier())

DisconnectionNotification = DictionaryVerifier()  # pylint: disable=C0103
DisconnectionNotification.add_required('type', LiteralVerifier('notification'))
DisconnectionNotification.add_required('operation', LiteralVerifier('disconnect'))
DisconnectionNotification.add_required('client', StringVerifier())
