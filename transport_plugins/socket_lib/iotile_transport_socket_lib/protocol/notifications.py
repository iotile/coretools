"""List of notifications handled by the WebSocket plugin."""

from iotile.core.utilities.schema_verify import BytesVerifier, DictionaryVerifier, Verifier, BooleanVerifier, IntVerifier,\
    StringVerifier


# Device found while scanning
ScanEvent = Verifier()

# Report
SerializedReport = DictionaryVerifier()
SerializedReport.add_required('encoded_report', BytesVerifier(encoding="base64"))
SerializedReport.add_required('received_time', Verifier())
SerializedReport.add_required('report_format', IntVerifier())
SerializedReport.add_required('origin', IntVerifier())

ReportEvent = DictionaryVerifier()
ReportEvent.add_required('connection_string', StringVerifier())
ReportEvent.add_required('serialized_report', SerializedReport)


DisconnectionEvent = DictionaryVerifier()
DisconnectionEvent.add_required('connection_string', StringVerifier())
DisconnectionEvent.add_required('reason', StringVerifier())
DisconnectionEvent.add_required('expected', BooleanVerifier())

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
