"""Schemas for all of the messages types that we support into the status server."""

from iotile.core.utilities.schema_verify import DictionaryVerifier, NoneVerifier, BytesVerifier, IntVerifier, StringVerifier, LiteralVerifier, OptionsVerifier, BooleanVerifier, FloatVerifier, ListVerifier

# Payloads that are shared among multiple messages
ServiceInfoPayload = DictionaryVerifier()
ServiceInfoPayload.add_required('short_name', StringVerifier())
ServiceInfoPayload.add_required('long_name', StringVerifier())
ServiceInfoPayload.add_required('preregistered', BooleanVerifier())

MessagePayload = DictionaryVerifier()
MessagePayload.add_required('level', IntVerifier())
MessagePayload.add_required('message', StringVerifier())
MessagePayload.add_required('created_time', FloatVerifier())
MessagePayload.add_required('now_time', FloatVerifier())
MessagePayload.add_optional('count', IntVerifier())
MessagePayload.add_optional('id', IntVerifier())

RPCCommandPayload = DictionaryVerifier()
RPCCommandPayload.add_required('rpc_id', IntVerifier())
RPCCommandPayload.add_required('payload', BytesVerifier())
RPCCommandPayload.add_required('response_uuid', StringVerifier())


# Commands that we support
HeartbeatCommand = DictionaryVerifier()
HeartbeatCommand.add_required('name', StringVerifier())
HeartbeatResponse = NoneVerifier()

SetAgentCommand = DictionaryVerifier()
SetAgentCommand.add_required('name', StringVerifier())
SetAgentResponse = NoneVerifier()


ServiceListCommand = NoneVerifier()
ServiceListResponse = ListVerifier(StringVerifier())

QueryStatusCommand = DictionaryVerifier()
QueryStatusCommand.add_required('name', StringVerifier())
QueryStatusResponse = DictionaryVerifier()
QueryStatusResponse.add_required('heartbeat_age', FloatVerifier())
QueryStatusResponse.add_required('numeric_status', IntVerifier())
QueryStatusResponse.add_required('string_status', StringVerifier())

QueryMessagesCommand = DictionaryVerifier()
QueryMessagesCommand.add_required('name', StringVerifier())
QueryMessagesResponse = ListVerifier(MessagePayload)

QueryHeadlineCommand = DictionaryVerifier()
QueryHeadlineCommand.add_required('name', StringVerifier())
QueryHeadlineResponse = OptionsVerifier(NoneVerifier(), MessagePayload)

QueryInfoCommand = DictionaryVerifier()
QueryInfoCommand.add_required('name', StringVerifier())
QueryInfoResponse = ServiceInfoPayload


RegisterServiceCommand = DictionaryVerifier()
RegisterServiceCommand.add_required('name', StringVerifier())
RegisterServiceCommand.add_required('long_name', StringVerifier())
RegisterServiceResponse = NoneVerifier()

UpdateStateCommand = DictionaryVerifier()
UpdateStateCommand.add_required('name', StringVerifier())
UpdateStateCommand.add_required('new_status', IntVerifier())
UpdateStateResponse = NoneVerifier()

PostMessageCommand = DictionaryVerifier()
PostMessageCommand.add_required('name', StringVerifier())
PostMessageCommand.add_required('level', IntVerifier())
PostMessageCommand.add_required('message', StringVerifier())
PostMessageResponse = NoneVerifier()

SetHeadlineCommand = DictionaryVerifier()
SetHeadlineCommand.add_required('name', StringVerifier())
SetHeadlineCommand.add_required('level', IntVerifier())
SetHeadlineCommand.add_required('message', StringVerifier())
SetHeadlineResponse = NoneVerifier()

SendRPCCommand = DictionaryVerifier()
SendRPCCommand.add_required('name', StringVerifier())
SendRPCCommand.add_required('rpc_id', IntVerifier())
SendRPCCommand.add_required('payload', BytesVerifier())
SendRPCCommand.add_required('timeout', FloatVerifier())
SendRPCResponse = DictionaryVerifier()
SendRPCResponse.add_required('result', StringVerifier())
SendRPCResponse.add_required('response', BytesVerifier())


RespondRPCCommand = DictionaryVerifier()
RespondRPCCommand.add_required('response_uuid', StringVerifier())
RespondRPCCommand.add_required('result', StringVerifier())
RespondRPCCommand.add_required('response', BytesVerifier())
RespondRPCResponse = NoneVerifier()


# Possible events

ServiceAddedEvent = DictionaryVerifier()
ServiceAddedEvent.add_required('service', StringVerifier())
ServiceAddedEvent.add_required('payload', ServiceInfoPayload)


ServiceStatusPayload = DictionaryVerifier()
ServiceStatusPayload.add_required('old_status', IntVerifier())
ServiceStatusPayload.add_required('new_status', IntVerifier())
ServiceStatusPayload.add_required('new_status_string', StringVerifier())

ServiceStatusEvent = DictionaryVerifier()
ServiceStatusEvent.add_required('service', StringVerifier())
ServiceStatusEvent.add_required('payload', ServiceStatusPayload)

NewMessageEvent = DictionaryVerifier()
NewMessageEvent.add_required('service', StringVerifier())
NewMessageEvent.add_required('payload', MessagePayload)

NewHeadlineEvent = NewMessageEvent


RPCCommandEvent = DictionaryVerifier()
RPCCommandEvent.add_required('service', StringVerifier())
RPCCommandEvent.add_required('payload', RPCCommandPayload)


HeartbeatReceivedEvent = DictionaryVerifier()
HeartbeatReceivedEvent.add_required('service', StringVerifier())
