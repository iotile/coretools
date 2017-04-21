"""Schemas for all of the messages types that we support into the status server."""

from iotile.core.utilities.schema_verify import DictionaryVerifier, IntVerifier, StringVerifier, LiteralVerifier, OptionsVerifier, BooleanVerifier, FloatVerifier

# Commands that we support
HeartbeatCommand = DictionaryVerifier()
HeartbeatCommand.add_required('type', LiteralVerifier('command'))
HeartbeatCommand.add_required('operation', LiteralVerifier('heartbeat'))
HeartbeatCommand.add_required('name', StringVerifier())
HeartbeatCommand.add_required('no_response', BooleanVerifier())

ServiceListCommand = DictionaryVerifier()
ServiceListCommand.add_required('type', LiteralVerifier('command'))
ServiceListCommand.add_required('operation', LiteralVerifier('list_services'))
ServiceListCommand.add_required('no_response', BooleanVerifier())

ServiceQueryCommand = DictionaryVerifier()
ServiceQueryCommand.add_required('type', LiteralVerifier('command'))
ServiceQueryCommand.add_required('operation', LiteralVerifier('query_status'))
ServiceQueryCommand.add_required('name', StringVerifier())
ServiceQueryCommand.add_required('no_response', BooleanVerifier())

QueryMessagesCommand = DictionaryVerifier()
QueryMessagesCommand.add_required('type', LiteralVerifier('command'))
QueryMessagesCommand.add_required('operation', LiteralVerifier('query_messages'))
QueryMessagesCommand.add_required('name', StringVerifier())
QueryMessagesCommand.add_required('no_response', BooleanVerifier())

QueryHeadlineCommand = DictionaryVerifier()
QueryHeadlineCommand.add_required('type', LiteralVerifier('command'))
QueryHeadlineCommand.add_required('operation', LiteralVerifier('query_headline'))
QueryHeadlineCommand.add_required('name', StringVerifier())
QueryHeadlineCommand.add_required('no_response', BooleanVerifier())

RegisterServiceCommand = DictionaryVerifier()
RegisterServiceCommand.add_required('type', LiteralVerifier('command'))
RegisterServiceCommand.add_required('operation', LiteralVerifier('register_service'))
RegisterServiceCommand.add_required('name', StringVerifier())
RegisterServiceCommand.add_required('long_name', StringVerifier())
RegisterServiceCommand.add_required('no_response', BooleanVerifier())

ServiceInfoCommand = DictionaryVerifier()
ServiceInfoCommand.add_required('type', LiteralVerifier('command'))
ServiceInfoCommand.add_required('operation', LiteralVerifier('query_info'))
ServiceInfoCommand.add_required('name', StringVerifier())
ServiceInfoCommand.add_required('no_response', BooleanVerifier())

UpdateStateCommand = DictionaryVerifier()
UpdateStateCommand.add_required('type', LiteralVerifier('command'))
UpdateStateCommand.add_required('operation', LiteralVerifier('update_state'))
UpdateStateCommand.add_required('name', StringVerifier())
UpdateStateCommand.add_required('new_status', IntVerifier())
UpdateStateCommand.add_required('no_response', BooleanVerifier())

PostMessageCommand = DictionaryVerifier()
PostMessageCommand.add_required('type', LiteralVerifier('command'))
PostMessageCommand.add_required('operation', LiteralVerifier('post_message'))
PostMessageCommand.add_required('name', StringVerifier())
PostMessageCommand.add_required('level', IntVerifier())
PostMessageCommand.add_required('message', StringVerifier())
PostMessageCommand.add_required('no_response', BooleanVerifier())

SetHeadlineCommand = DictionaryVerifier()
SetHeadlineCommand.add_required('type', LiteralVerifier('command'))
SetHeadlineCommand.add_required('operation', LiteralVerifier('set_headline'))
SetHeadlineCommand.add_required('name', StringVerifier())
SetHeadlineCommand.add_required('level', IntVerifier())
SetHeadlineCommand.add_required('message', StringVerifier())
SetHeadlineCommand.add_required('created_time', FloatVerifier())
SetHeadlineCommand.add_required('now_time', FloatVerifier())
SetHeadlineCommand.add_required('no_response', BooleanVerifier())

CommandMessage = OptionsVerifier(HeartbeatCommand, SetHeadlineCommand, QueryHeadlineCommand, QueryMessagesCommand, PostMessageCommand, UpdateStateCommand, ServiceInfoCommand, RegisterServiceCommand, ServiceListCommand, ServiceQueryCommand)

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
