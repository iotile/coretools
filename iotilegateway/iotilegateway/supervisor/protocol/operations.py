"""All supported command and event names."""

CMD_HEARTBEAT = 'heartbeat'
CMD_LIST_SERVICES = 'list_services'
CMD_QUERY_STATUS = 'query_status'
CMD_QUERY_MESSAGES = 'query_messages'
CMD_QUERY_HEADLINE = 'query_headline'
CMD_QUERY_INFO = 'query_info'

CMD_REGISTER_SERVICE = 'register_service'
CMD_SET_AGENT = 'set_agent'
CMD_UPDATE_STATE = 'update_state'
CMD_POST_MESSAGE = 'post_message'
CMD_SET_HEADLINE = 'set_headline'
CMD_SEND_RPC = 'send_rpc'
CMD_RESPOND_RPC = 'respond_rpc'


EVENT_STATUS_CHANGED = 'state_change'
EVENT_SERVICE_ADDED = 'new_service'
EVENT_HEARTBEAT_RECEIVED = 'heartbeat'
EVENT_NEW_MESSAGE = 'new_message'
EVENT_NEW_HEADLINE = 'new_headline'
EVENT_RPC_COMMAND = 'rpc_command'
