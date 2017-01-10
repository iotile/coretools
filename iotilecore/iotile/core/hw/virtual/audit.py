"""A list of event codes that are logged to the audit log by virtual devices for verification purposes
"""

from collections import namedtuple

AuditEvent = namedtuple('AuditEvent', ['name', 'message', 'required_keys', 'optional_keys'])

ClientConnected = AuditEvent('ClientConnected', 'A client connected to this device', frozenset(), frozenset())
ClientDisconnected = AuditEvent('ClientDisconnected', 'A client disconnected from this device', frozenset(), frozenset())
RPCInterfaceOpened = AuditEvent('RPCInterfaceOpened', 'A client opened the RPC interface on this device', frozenset(), frozenset())
StreamingInterfaceOpened = AuditEvent('StreamingInterfaceOpened', 'A client opened the streaming interface on this device', frozenset(), frozenset())
StreamingInterfaceClosed = AuditEvent('StreamingInterfaceClosed', 'A client closed the streaming interface on this device', frozenset(), frozenset())
ReportStreamed = AuditEvent('ReportStreamed', 'The device streamed a report to the client, report=%(report)s', frozenset(['report']), frozenset())
ErrorStreamingReport = AuditEvent('ErrorStreamingReport', 'There was an error sending a report to the client, further streaming has been stopped', frozenset(), frozenset())
RPCReceived = AuditEvent('RPCReceived', 'An RPC has been processed (id=%(rpc_id)s, address=%(address)s, payload="%(payload)s"), status=%(status)d, response="%(response)s"', frozenset(['rpc_id', 'address', 'payload', 'status', 'response']), frozenset())
