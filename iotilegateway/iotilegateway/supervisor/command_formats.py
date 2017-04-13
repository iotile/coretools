"""Schemas for all of the messages types that we support into the status server."""

from iotile.core.utilities.schema_verify import DictionaryVerifier, IntVerifier, StringVerifier, LiteralVerifier, OptionsVerifier, BooleanVerifier

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

CommandMessage = OptionsVerifier(HeartbeatCommand, QueryMessagesCommand, PostMessageCommand, UpdateStateCommand, ServiceInfoCommand, RegisterServiceCommand, ServiceListCommand, ServiceQueryCommand)

# Possible response and notification payloads
ServiceInfoPayload = DictionaryVerifier()
ServiceInfoPayload.add_required('short_name', StringVerifier())
ServiceInfoPayload.add_required('long_name', StringVerifier())
ServiceInfoPayload.add_required('preregistered', BooleanVerifier())

ServiceStatusPayload = DictionaryVerifier()
ServiceStatusPayload.add_required('old_status', IntVerifier())
ServiceStatusPayload.add_required('new_status', IntVerifier())
ServiceStatusPayload.add_required('new_status_string', StringVerifier())

NewMessagePayload = DictionaryVerifier()
NewMessagePayload.add_required('level', IntVerifier())
NewMessagePayload.add_required('message', StringVerifier())

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
NewMessage.add_required('payload', NewMessagePayload)
