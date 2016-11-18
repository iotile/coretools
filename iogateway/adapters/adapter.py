class DeviceAdapter (object):
    """Classes that encapsulate access to IOTile devices over a particular communication channel
    """

    def __init__(self):
        self.id = -1

        self.callbacks = {}
        self.callbacks['on_scan'] = set()
        self.callbacks['on_disconnect'] = set()

    def set_id(self, adapter_id):
        """Set an ID that this adapater uses to identify itself when making callbacks
        """
        
        self.id = adapter_id

    def add_callback(self, name, func):
        """Add a callback when Device events happen

        Args:
            name (str): currently support 'on_scan' and 'on_disconnect'
            func (callable): the function that should be called
        """

        if name not in self.callbacks:
            raise ValueError("Unknown callback name: %s" % name)

        self.callbacks[name].add(func)

    def _trigger_callback(self, name, *args, **kwargs):
        for func in self.callbacks[name]:
            func(*args, **kwargs)
