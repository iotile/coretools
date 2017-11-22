"""A virtual tile that delegates all RPC calls to a named service."""

from iotile.core.exceptions import InternalError
from iotile.core.hw.virtual import VirtualTile, RPCNotFoundError, RPCInvalidArgumentsError, RPCInvalidReturnValueError, TileNotFoundError
from iotilegateway.supervisor import ServiceStatusClient

class ServiceDelegateTile(VirtualTile):
    """A tile that delegates all RPCs to a service using the IOTileSupervisor.

    Args:
        address (int): The address that we are being created at
        args (dict): Configuration arguments with the following required keys:
            name (str): The 6 byte name we should return for this tile
            service (str): The short name of the service that we should forward
                RPCs on to when someone calls an RPC on us.
            url (str): The URL of the supervisor that we should connect to.  If
                no url is specified, the default is 127.0.0.1:9400/services which
                is the supervisor default.
    """

    def __init__(self, address, args, device=None):
        name = args['name']
        service = args['service']
        url = args.get('url', 'ws://127.0.0.1:9400/services')

        super(ServiceDelegateTile, self).__init__(address, name)

        self._service = service
        self._client = ServiceStatusClient(url)

    def has_rpc(self, rpc_id):
        """Check if an RPC is defined.

        Args:
            rpc_id (int): The RPC to check

        Returns:
            bool: Whether it exists
        """

        # Since we don't know what RPCs are defined in the service on the
        # other side of the supervisor, we need to actually try to call
        # each RPC and fail at that point if they don't exist.
        return True

    def call_rpc(self, rpc_id, payload=bytes()):
        """Call an RPC by its ID.

        Args:
            rpc_id (int): The number of the RPC
            payload (bytes): A byte string of payload parameters up to 20 bytes

        Returns:
            str: The response payload from the RPC
        """

        # If we define the RPC locally, call that one.  We use this for reporting
        # our status
        if super(ServiceDelegateTile, self).has_rpc(rpc_id):
            return super(ServiceDelegateTile, self).call_rpc(rpc_id, payload)

        # FIXME: We set the timeout here to a very large number since we don't
        # know what an appropriate timeout is and don't want to restrict the
        # run time of RPCs that could be long running.  The caller of the RPC
        # through the tile will know what an appropriate timeout is for the
        # RPC that they are trying to call.
        resp = self._client.send_rpc(self._service, rpc_id, payload, timeout=120.0)
        result = resp['result']

        if result == 'success':
            return resp['response']
        elif result == 'service_not_found':
            raise TileNotFoundError("Could not find service by name", name=self._service)
        elif result == 'rpc_not_found':
            raise RPCNotFoundError("Could not find RPC on service", name=self._service, rpc_id=rpc_id)
        elif result == 'invalid_arguments':
            raise RPCInvalidArgumentsError("Invalid arguments to RPC", name=self._service, rpc_id=rpc_id)
        elif result == 'invalid_response':
            raise RPCInvalidReturnValueError("Invalid response from RPC", name=self._service, rpc_id=rpc_id)
        elif result == 'execution_exception':
            raise InternalError("Exception raised during processing RPC", name=self._service, rpc_id=rpc_id)
        else:
            raise InternalError("Unknown response received from delegated RPC", name=self._service, rpc_id=rpc_id, result=result)
