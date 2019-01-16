import json
import os
from iotile.mock.devices import ReportTestDevice, TracingTestDevice


# ====== Report test device ======

def build_report_device():
    with open(os.path.join(os.path.dirname(__file__), 'report_device_config.json'), "rb") as conf_file:
        config = json.load(conf_file)

    return ReportTestDevice(config['device'])


def get_report_device_string():
    config_path = os.path.join(os.path.dirname(__file__), 'report_device_config.json')

    return 'report_test@{}'.format(config_path)


# ====== Tracing test device ======

def build_tracing_device():
    with open(os.path.join(os.path.dirname(__file__), 'tracing_device_config.json'), "rb") as conf_file:
        config = json.load(conf_file)

    return TracingTestDevice(config['device'])


def get_tracing_device_string():
    config_path = os.path.join(os.path.dirname(__file__), 'tracing_device_config.json')

    return 'tracing_test@{}'.format(config_path)
