"""List of notifications handled by the WebSocket plugin."""

from iotile.core.utilities.schema_verify import BytesVerifier, DictionaryVerifier, Verifier, IntVerifier,\
    LiteralVerifier, StringVerifier


# Device found while scanning
ScanEvent = Verifier()

# Report
ReportEvent = DictionaryVerifier()
ReportEvent.add_required('connection_string', StringVerifier())
ReportEvent.add_required('payload', BytesVerifier(encoding="base64"))
ReportEvent.add_required('received_time', Verifier())

# Trace
TraceEvent = DictionaryVerifier()
TraceEvent.add_required('connection_string', StringVerifier())
TraceEvent.add_required('payload', BytesVerifier(encoding="base64"))

# Script and debug progress
ProgressEvent = DictionaryVerifier()
ProgressEvent.add_required('connection_string', StringVerifier())
ProgressEvent.add_required('operation', StringVerifier())
ProgressEvent.add_required('done_count', IntVerifier())
ProgressEvent.add_required('total_count', IntVerifier())
