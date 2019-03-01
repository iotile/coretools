"""Schemas for all of the messages types that we support into the status server."""

from iotile.core.utilities.schema_verify import DictionaryVerifier, BytesVerifier, IntVerifier, StringVerifier, LiteralVerifier, OptionsVerifier, BooleanVerifier, FloatVerifier

# The basic form of a command packet that all commands derive from
BasicCommand = DictionaryVerifier()
BasicCommand.add_required('type', LiteralVerifier('command'))
BasicCommand.add_required('no_response', BooleanVerifier())

# Commands that we support
HeartbeatCommand = BasicCommand.clone()
HeartbeatCommand.add_required('operation', LiteralVerifier('heartbeat'))
HeartbeatCommand.add_required('name', StringVerifier())

ServiceListCommand = BasicCommand.clone()
ServiceListCommand.add_required('operation', LiteralVerifier('list_services'))

SetAgentCommand = BasicCommand.clone()
SetAgentCommand.add_required('operation', LiteralVerifier('set_agent'))
SetAgentCommand.add_required('name', StringVerifier())

ServiceQueryCommand = BasicCommand.clone()
ServiceQueryCommand.add_required('operation', LiteralVerifier('query_status'))
ServiceQueryCommand.add_required('name', StringVerifier())

QueryMessagesCommand = BasicCommand.clone()
QueryMessagesCommand.add_required('operation', LiteralVerifier('query_messages'))
QueryMessagesCommand.add_required('name', StringVerifier())

QueryHeadlineCommand = BasicCommand.clone()
QueryHeadlineCommand.add_required('operation', LiteralVerifier('query_headline'))
QueryHeadlineCommand.add_required('name', StringVerifier())

RegisterServiceCommand = BasicCommand.clone()
RegisterServiceCommand.add_required('operation', LiteralVerifier('register_service'))
RegisterServiceCommand.add_required('name', StringVerifier())
RegisterServiceCommand.add_required('long_name', StringVerifier())

ServiceInfoCommand = BasicCommand.clone()
ServiceInfoCommand.add_required('operation', LiteralVerifier('query_info'))
ServiceInfoCommand.add_required('name', StringVerifier())

UpdateStateCommand = BasicCommand.clone()
UpdateStateCommand.add_required('operation', LiteralVerifier('update_state'))
UpdateStateCommand.add_required('name', StringVerifier())
UpdateStateCommand.add_required('new_status', IntVerifier())

PostMessageCommand = BasicCommand.clone()
PostMessageCommand.add_required('operation', LiteralVerifier('post_message'))
PostMessageCommand.add_required('name', StringVerifier())
PostMessageCommand.add_required('level', IntVerifier())
PostMessageCommand.add_required('message', StringVerifier())

SetHeadlineCommand = BasicCommand.clone()
SetHeadlineCommand.add_required('operation', LiteralVerifier('set_headline'))
SetHeadlineCommand.add_required('name', StringVerifier())
SetHeadlineCommand.add_required('level', IntVerifier())
SetHeadlineCommand.add_required('message', StringVerifier())
SetHeadlineCommand.add_required('created_time', FloatVerifier())
SetHeadlineCommand.add_required('now_time', FloatVerifier())

SendRPCCommand = BasicCommand.clone()
SendRPCCommand.add_required('operation', LiteralVerifier('send_rpc'))
SendRPCCommand.add_required('name', StringVerifier())
SendRPCCommand.add_required('rpc_id', IntVerifier())
SendRPCCommand.add_required('payload', BytesVerifier())
SendRPCCommand.add_required('timeout', FloatVerifier())

SendRPCResponse = BasicCommand.clone()
SendRPCResponse.add_required('operation', LiteralVerifier('rpc_response'))
SendRPCResponse.add_required('response_uuid', StringVerifier())
SendRPCResponse.add_required('result', StringVerifier())
SendRPCResponse.add_required('response', BytesVerifier())

CommandMessage = OptionsVerifier(SetAgentCommand, SendRPCCommand, SendRPCResponse, HeartbeatCommand, SetHeadlineCommand, QueryHeadlineCommand, QueryMessagesCommand, PostMessageCommand, UpdateStateCommand, ServiceInfoCommand, RegisterServiceCommand, ServiceListCommand, ServiceQueryCommand)

# Possible response and notification payloads
ServiceInfoPayload = DictionaryVerifier()
ServiceInfoPayload.add_required('short_name', StringVerifier())
ServiceInfoPayload.add_required('long_name', StringVerifier())
ServiceInfoPayload.add_required('preregistered', BooleanVerifier())

ServiceStatusPayload = DictionaryVerifier()
ServiceStatusPayload.add_required('old_status', IntVerifier())
ServiceStatusPayload.add_required('new_status', IntVerifier())
ServiceStatusPayload.add_required('new_status_string', StringVerifier())

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

RPCResponsePayload = DictionaryVerifier()
RPCResponsePayload.add_required('payload', BytesVerifier())
RPCResponsePayload.add_required('result', StringVerifier())
RPCResponsePayload.add_required('response_uuid', StringVerifier())

# Notifications that the SupervisorService can push
ServiceStatusChanged = DictionaryVerifier()
ServiceStatusChanged.add_required('type', LiteralVerifier('notification'))
ServiceStatusChanged.add_required('operation', LiteralVerifier('state_change'))
ServiceStatusChanged.add_required('name', StringVerifier())
ServiceStatusChanged.add_required('payload', ServiceStatusPayload)

ServiceAdded = DictionaryVerifier()
ServiceAdded.add_required('type', LiteralVerifier('notification'))
ServiceAdded.add_required('operation', LiteralVerifier('new_service'))
ServiceAdded.add_required('name', StringVerifier())
ServiceAdded.add_required('payload', ServiceInfoPayload)

HeartbeatReceived = DictionaryVerifier()
HeartbeatReceived.add_required('type', LiteralVerifier('notification'))
HeartbeatReceived.add_required('operation', LiteralVerifier('heartbeat'))
HeartbeatReceived.add_required('name', StringVerifier())

NewMessage = DictionaryVerifier()
NewMessage.add_required('type', LiteralVerifier('notification'))
NewMessage.add_required('operation', LiteralVerifier('new_message'))
NewMessage.add_required('name', StringVerifier())
NewMessage.add_required('payload', MessagePayload)

NewHeadline = DictionaryVerifier()
NewHeadline.add_required('type', LiteralVerifier('notification'))
NewHeadline.add_required('operation', LiteralVerifier('new_headline'))
NewHeadline.add_required('name', StringVerifier())
NewHeadline.add_required('payload', MessagePayload)

RPCCommand = DictionaryVerifier()
RPCCommand.add_required('type', LiteralVerifier('notification'))
RPCCommand.add_required('operation', LiteralVerifier('rpc_command'))
RPCCommand.add_required('name', StringVerifier())
RPCCommand.add_required('payload', RPCCommandPayload)

RPCResponse = DictionaryVerifier()
RPCResponse.add_required('type', LiteralVerifier('notification'))
RPCResponse.add_required('operation', LiteralVerifier('rpc_response'))
RPCResponse.add_required('name', StringVerifier())
RPCResponse.add_required('payload', RPCResponsePayload)
