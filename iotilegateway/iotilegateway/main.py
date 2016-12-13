import signal
import logging
import tornado.ioloop
from tornado.options import define, options, parse_command_line
import serial.tools.list_ports
from wshandler import WebSocketHandler
from webhandler import IndexHandler
import device
import pkg_resources

define("port", default=5120, help="run server on given port", type=int)

should_close = False
device_manager = None
BLED112Adapter = None

def quit_signal_handler(signum, frame):
    global should_close

    should_close = True
    log = logging.getLogger('tornado.general')
    log.critical('Received stop signal, attempting to stop')

def try_quit():
    global should_close

    if not should_close:
        return

    log = logging.getLogger('tornado.general')

    if device_manager is not None:
        log.critical('Stopping BLE Adapters')
        device_manager.stop()

    tornado.ioloop.IOLoop.instance().stop()
    log.critical('Stopping event loop and shutting down')

def find_bled112_devices():
    found_devs = []

    #Look for BLED112 dongles on this computer and start an instance on each one
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if not hasattr(p, 'pid') or not hasattr(p, 'vid'):
            continue

        #Check if the device matches the BLED112's PID/VID combination
        #FIXME: This requires a newer version of pyserial that has pid and vid exposed
        if (p.pid == 1 and p.vid == 9304):
            found_devs.append(p.device)

    return found_devs

def main():
    global device_manager
    
    log = logging.getLogger('tornado.general')

    #Find BLED112 adapter
    for entry in pkg_resources.iter_entry_points('iotile.device_adapter', 'bled112'):
        BLED112Adapter = entry.load()
        break

    if BLED112Adapter is None:
        raise RuntimeError("BLED112 adapter is not installed!")

    parse_command_line()
    loop = tornado.ioloop.IOLoop.instance()

    signal.signal(signal.SIGINT, quit_signal_handler)

    device_manager = device.DeviceManager(loop)

    app = tornado.web.Application([
        (r'/', IndexHandler, {'manager': device_manager}),
        (r'/iotile/v1', WebSocketHandler, {'manager': device_manager}),
    ])

    app.listen(options.port)
    tornado.ioloop.PeriodicCallback(try_quit, 100).start()

    logging.getLogger('server').critical("Starting websocket server on port %d" % options.port)

    #Take control of all BLED112 devices attached to this computer
    devs = find_bled112_devices()
    for dev in devs:
        bled_wrapper = BLED112Adapter(dev)
        device_manager.add_adapter(bled_wrapper)

    loop.start()

    log.critical("Done stopping loop")
