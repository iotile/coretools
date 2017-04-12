"""Schemas for all of the messages types that we support into the status server
"""

from iotile.core.utilities.schema_verify import DictionaryVerifier, IntVerifier, StringVerifier, LiteralVerifier, OptionsVerifier

HeartbeatCommand = DictionaryVerifier()
HeartbeatCommand.add_required('type', LiteralVerifier('command'))
HeartbeatCommand.add_required('operation', LiteralVerifier('heartbeat'))
HeartbeatCommand.add_required('name', StringVerifier())

ServiceListCommand = DictionaryVerifier()
ServiceListCommand.add_required('type', LiteralVerifier('command'))
ServiceListCommand.add_required('operation', LiteralVerifier('list_services'))

ServiceQueryCommand = DictionaryVerifier()
ServiceQueryCommand.add_required('type', LiteralVerifier('command'))
ServiceQueryCommand.add_required('operation', LiteralVerifier('query_status'))
ServiceQueryCommand.add_required('name', StringVerifier())

CommandMessage = OptionsVerifier(HeartbeatCommand, ServiceListCommand, ServiceQueryCommand)

# Notifications that the SupervisorService can push
ServiceStatusChanged = DictionaryVerifier()
ServiceStatusChanged.add_required('type', LiteralVerifier('notification'))
ServiceStatusChanged.add_required('operation', LiteralVerifier('status_changed'))
ServiceStatusChanged.add_required('name', StringVerifier())
ServiceStatusChanged.add_required('old_status', IntVerifier())
ServiceStatusChanged.add_required('new_status', IntVerifier())
ServiceStatusChanged.add_required('new_status_string', StringVerifier())

