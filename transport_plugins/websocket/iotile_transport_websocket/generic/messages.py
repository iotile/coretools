"""The classes of messages supported by this websocket impementation."""

from iotile.core.utilities.schema_verify import Verifier, NoneVerifier, DictionaryVerifier, StringVerifier, LiteralVerifier, OptionsVerifier

# The prescribed schema of command response messages
# Messages with this format are automatically processed inside the ValidatingWSClient
COMMAND = DictionaryVerifier()
COMMAND.add_required('type', LiteralVerifier('command'))
COMMAND.add_required('operation', StringVerifier())
COMMAND.add_required('uuid', StringVerifier())
COMMAND.add_optional('payload', Verifier())

SUCCESSFUL_RESPONSE = DictionaryVerifier()
SUCCESSFUL_RESPONSE.add_required('uuid', StringVerifier())
SUCCESSFUL_RESPONSE.add_required('type', LiteralVerifier('response'))
SUCCESSFUL_RESPONSE.add_required('success', LiteralVerifier(True))
SUCCESSFUL_RESPONSE.add_optional('payload', Verifier())

FAILURE_RESPONSE = DictionaryVerifier()
FAILURE_RESPONSE.add_required('type', LiteralVerifier('response'))
FAILURE_RESPONSE.add_required('uuid', StringVerifier())
FAILURE_RESPONSE.add_required('success', LiteralVerifier(False))
FAILURE_RESPONSE.add_required('reason', StringVerifier())
FAILURE_RESPONSE.add_required('exception_class', OptionsVerifier(StringVerifier(), NoneVerifier()))

RESPONSE = OptionsVerifier(SUCCESSFUL_RESPONSE, FAILURE_RESPONSE)

EVENT = DictionaryVerifier()
EVENT.add_required('type', LiteralVerifier('event'))
EVENT.add_required('name', StringVerifier())
EVENT.add_optional('payload', Verifier())

VALID_SERVER_MESSAGE = OptionsVerifier(RESPONSE, EVENT)
VALID_CLIENT_MESSAGE = OptionsVerifier(COMMAND)
