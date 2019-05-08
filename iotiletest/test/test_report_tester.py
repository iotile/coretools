from iotile.mock.devices.report_test_device import ReportTestDevice

def test_report_args():
    """Make sure report arguments are properly parsed and used
    """

    args = {
        "iotile_id": "1",
        "reading_start": 100,
        "num_readings": 107,
        "stream_id": "5001",
        "format": "signed_list",
        "report_length": 10,
        "signing_method": 0,
        'starting_timestamp': 10,
        'starting_id': 15
    }

    dev = ReportTestDevice(args)

    assert dev.start_timestamp == 10
    assert dev.start_id == 15

    reports = dev._open_streaming_interface()

    assert len(reports) == 11

    report1 = reports[0]

    assert report1.lowest_id == 15
    assert report1.highest_id == 24
    assert len(report1.visible_readings) == 10

    read = report1.visible_readings[0]
    assert read.stream == 0x5001
    assert read.value == 100
    assert read.raw_time == 10
