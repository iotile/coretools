"""All known and accepted messages that can be sent over AWS IOT."""

from iotile.core.utilities.schema_verify import Verifier, EnumVerifier, ListVerifier, BytesVerifier, IntVerifier, LiteralVerifier, FloatVerifier, DictionaryVerifier, StringVerifier


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

# All responses that we support
SuccessfulCommandResponse = DictionaryVerifier()  # pylint: disable=C0103
SuccessfulCommandResponse.add_required('type', LiteralVerifier('response'))
SuccessfulCommandResponse.add_required('client', StringVerifier())
SuccessfulCommandResponse.add_required('success', LiteralVerifier(True))

FailedCommandResponse = DictionaryVerifier()  # pylint: disable=C0103
FailedCommandResponse.add_required('type', LiteralVerifier('response'))
FailedCommandResponse.add_required('client', StringVerifier())
FailedCommandResponse.add_required('success', LiteralVerifier(False))
FailedCommandResponse.add_required('failure_reason', StringVerifier())

RPCPayloadResponse = DictionaryVerifier()  # pylint: disable=C0103
RPCPayloadResponse.add_required('type', LiteralVerifier('response'))
RPCPayloadResponse.add_required('client', StringVerifier())
RPCPayloadResponse.add_required('success', LiteralVerifier(True))
RPCPayloadResponse.add_required('status', IntVerifier())
RPCPayloadResponse.add_required('payload', BytesVerifier(encoding='hex'))

ProbeResponse = DictionaryVerifier()  # pylint: disable=C0103
ProbeResponse.add_required('type', LiteralVerifier('response'))
ProbeResponse.add_required('client', StringVerifier())
ProbeResponse.add_required('success', LiteralVerifier(True))
ProbeResponse.add_required('devices', ListVerifier(Verifier()))

ConnectionResponse = DictionaryVerifier()  # pylint: disable=C0103
ConnectionResponse.add_required('type', LiteralVerifier('response'))
ConnectionResponse.add_required('client', StringVerifier())
ConnectionResponse.add_required('success', LiteralVerifier(True))
ConnectionResponse.add_required('connection_id', IntVerifier())
