## IOTile Transport Websocket

The IOTile Transport Websocket plugin allows to connect to a gateway via websockets
and to control nodes as if you were the gateway.
It contains a WebSocketDeviceAdapter, a WebSocketVirtualInterface and some tools needed
to make the whole thing work.

If you want to use the websocket gateway agent, you'll need to have the `iotile-gateway`
package **>=1.6.0**.

---

This includes `Pithikos/python-websocket-server` which is licensed under MIT and used in
accordance with its license from the repository at this link :
[Pithikos/python-websocket-server](https://github.com/Pithikos/python-websocket-server).
