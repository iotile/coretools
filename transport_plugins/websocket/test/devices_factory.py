from iotile.mock.devices import ReportTestDevice, TracingTestDevice


def build_report_device(iotile_id):
    config = {
        "iotile_id": iotile_id,
        "num_readings": 6,
        "format": "signed_list",
        "report_length": 2,
        "stream_id": "0x2000"
    }

    return ReportTestDevice(config)


def build_tracing_device(iotile_id, ascii_data):
    config = {
        "iotile_id": iotile_id,
        "ascii_data": ascii_data
    }

    return TracingTestDevice(config)
