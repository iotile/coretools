# Final boolean is whether the package is python 3 clean

class Component(object):
    def __init__(self, distro, path, compat="universal"):
        if compat not in ('universal', 'python2', 'python3'):
            raise ValueError("Unknown python compatibility: %s" % compat)

        self.distro = distro
        self.path = path
        self.compat = compat
        self.py3k_clean = compat in ('universal', 'python3')
        self.py2k_clean = compat in ('universal', 'python2')


comp_names = {
    'iotilecore': Component('iotile-core', 'iotilecore'),
    'iotilebuild': Component('iotile-build', 'iotilebuild'),
    'iotiletest': Component('iotile-test', 'iotiletest'),
    'iotilegateway': Component('iotile-gateway', 'iotilegateway'),
    'iotilesensorgraph': Component('iotile-sensorgraph', 'iotilesensorgraph'),
    'iotileemulate': Component('iotile-emulate', 'iotileemulate', compat="python3"),
    'iotileship' : Component('iotile-ship', 'iotileship'),
    'iotile_transport_bled112': Component('iotile-transport-bled112', 'transport_plugins/bled112'),
    'iotile_transport_awsiot': Component('iotile-transport-awsiot', 'transport_plugins/awsiot', compat="python2"),
    'iotile_transport_websocket': Component('iotile-transport-websocket', 'transport_plugins/websocket'),
    'iotile_transport_native_ble': Component('iotile-transport-native-ble', 'transport_plugins/native_ble'),
    'iotile_transport_jlink': Component('iotile-transport-jlink', 'transport_plugins/jlink', compat="python2"),
    'iotile_ext_cloud': Component('iotile-ext-cloud', 'iotile_ext_cloud')
}
