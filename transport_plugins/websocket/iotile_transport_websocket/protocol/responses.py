"""List of responses handled by the WebSocket plugin."""

from iotile.core.utilities.schema_verify import BooleanVerifier, BytesVerifier, DictionaryVerifier, Verifier, \
    IntVerifier, LiteralVerifier, OptionsVerifier, StringVerifier
from . import operations

# Generic responses
Basic = DictionaryVerifier()
Basic.add_required('type', LiteralVerifier('response'))
Basic.add_required('connection_string', StringVerifier())

SuccessfulCommand = Basic.clone()
SuccessfulCommand.add_required('success', BooleanVerifier(True))

FailedCommand = Basic.clone()
FailedCommand.add_required('success', BooleanVerifier(False))
FailedCommand.add_required('failure_reason', StringVerifier())

# Connect
SuccessfulConnect = SuccessfulCommand.clone()
SuccessfulConnect.add_required('operation', LiteralVerifier(operations.CONNECT))

FailedConnect = FailedCommand.clone()
FailedConnect.add_required('operation', LiteralVerifier(operations.CONNECT))

Connect = OptionsVerifier(SuccessfulConnect, FailedConnect)

# Disconnect
SuccessfulDisconnect = SuccessfulCommand.clone()
SuccessfulDisconnect.add_required('operation', LiteralVerifier(operations.DISCONNECT))

FailedDisconnect = FailedCommand.clone()
FailedDisconnect.add_required('operation', LiteralVerifier(operations.DISCONNECT))

Disconnect = OptionsVerifier(SuccessfulDisconnect, FailedDisconnect)

# Scan
SuccessfulScan = DictionaryVerifier()
SuccessfulScan.add_required('type', LiteralVerifier('response'))
SuccessfulScan.add_required('operation', LiteralVerifier(operations.SCAN))
SuccessfulScan.add_required('success', BooleanVerifier(True))

FailedScan = DictionaryVerifier()
FailedScan.add_required('type', LiteralVerifier('response'))
FailedScan.add_required('operation', LiteralVerifier(operations.SCAN))
FailedScan.add_required('success', BooleanVerifier(False))
FailedScan.add_required('failure_reason', StringVerifier())

Scan = OptionsVerifier(SuccessfulScan, FailedScan)

# Open interface
SuccessfulOpenInterface = SuccessfulCommand.clone()
SuccessfulOpenInterface.add_required('operation', LiteralVerifier(operations.OPEN_INTERFACE))

FailedOpenInterface = FailedCommand.clone()
FailedOpenInterface.add_required('operation', LiteralVerifier(operations.OPEN_INTERFACE))

OpenInterface = OptionsVerifier(SuccessfulOpenInterface, FailedOpenInterface)

# Close interface
SuccessfulCloseInterface = SuccessfulCommand.clone()
SuccessfulCloseInterface.add_required('operation', LiteralVerifier(operations.CLOSE_INTERFACE))

FailedCloseInterface = FailedCommand.clone()
FailedCloseInterface.add_required('operation', LiteralVerifier(operations.CLOSE_INTERFACE))

CloseInterface = OptionsVerifier(SuccessfulCloseInterface, FailedCloseInterface)

# Send RPC
SuccessfulSendRPC = SuccessfulCommand.clone()
SuccessfulSendRPC.add_required('operation', LiteralVerifier(operations.SEND_RPC))
SuccessfulSendRPC.add_required('return_value', BytesVerifier(encoding="base64"))
SuccessfulSendRPC.add_required('status', IntVerifier())

FailedSendRPC = FailedCommand.clone()
FailedSendRPC.add_required('operation', LiteralVerifier(operations.SEND_RPC))

SendRPC = OptionsVerifier(SuccessfulSendRPC, FailedSendRPC)

# Send script
SuccessfulSendScript = SuccessfulCommand.clone()
SuccessfulSendScript.add_required('operation', LiteralVerifier(operations.SEND_SCRIPT))

FailedSendScript = FailedCommand.clone()
FailedSendScript.add_required('operation', LiteralVerifier(operations.SEND_SCRIPT))

SendScript = OptionsVerifier(SuccessfulSendScript, FailedSendScript)

# Unknown
SuccessfulUnknownOperation = DictionaryVerifier()
SuccessfulUnknownOperation.add_required('type', Verifier())
SuccessfulUnknownOperation.add_required('operation', LiteralVerifier(operations.UNKNOWN))
SuccessfulUnknownOperation.add_required('success', BooleanVerifier(True))
SuccessfulUnknownOperation.add_optional('payload', Verifier())

FailedUnknownOperation = DictionaryVerifier()
FailedUnknownOperation.add_required('type', Verifier())
FailedUnknownOperation.add_required('operation', LiteralVerifier(operations.UNKNOWN))
FailedUnknownOperation.add_required('success', BooleanVerifier(False))
FailedUnknownOperation.add_required('failure_reason', StringVerifier())
FailedUnknownOperation.add_optional('payload', Verifier())

Unknown = OptionsVerifier(SuccessfulUnknownOperation, FailedUnknownOperation)
