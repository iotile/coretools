import tornado.ioloop
import signal
import logging
from adapters.bled112.bled112 import BLED112Adapter
import device
import serial.tools.list_ports
from wshandler import WebSocketHandler
from webhandler import IndexHandler
from tornado.options import define, options, parse_command_line

define("port", default=5120, help="run server on given port", type=int)

should_close = False
device_manager = None

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
        #Check if the device matches the BLED112's PID/VID combination
        if (p.pid == 1 and p.vid == 9304):
            found_devs.append(p.device)

    return found_devs

if __name__ == '__main__':
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
        bled_wrapper = bled112.BLED112Adapter(dev)
        device_manager.add_adapter(bled_wrapper)

    loop.start()
