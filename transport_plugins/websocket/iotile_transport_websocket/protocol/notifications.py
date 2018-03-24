from iotile.core.utilities.schema_verify import DictionaryVerifier, Verifier, IntVerifier,\
    LiteralVerifier, StringVerifier
import operations

Basic = DictionaryVerifier()
Basic.add_required('type', LiteralVerifier('notification'))

# Device found while scanning
DeviceFound = Basic.clone()
DeviceFound.add_required('operation', LiteralVerifier(operations.NOTIFY_DEVICE_FOUND))
DeviceFound.add_required('device', Verifier())

# Report
Report = Basic.clone()
Report.add_required('operation', LiteralVerifier(operations.NOTIFY_REPORT))
Report.add_required('connection_string', StringVerifier())
Report.add_required('payload', Verifier())

# Trace
Trace = Basic.clone()
Trace.add_required('operation', LiteralVerifier(operations.NOTIFY_TRACE))
Trace.add_required('connection_string', StringVerifier())
Trace.add_required('payload', Verifier())

# Script progress
Progress = Basic.clone()
Progress.add_required('operation', LiteralVerifier(operations.NOTIFY_PROGRESS))
Progress.add_required('connection_string', StringVerifier())
Progress.add_required('done_count', IntVerifier())
Progress.add_required('total_count', IntVerifier())
