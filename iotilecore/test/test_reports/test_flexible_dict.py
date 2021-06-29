import msgpack
from datetime import datetime
from iotile.core.hw.reports import FlexibleDictionaryReport


def test_decoding_flexible_report():
    """Make sure we can decode a msgpack encoded report."""

    data = {
        "format": "v100",
        "device": 10,
        "streamer_index": 100,
        "streamer_selector": 65536,
        "device_sent_timestamp": 1,
        "incremental_id": 1,
        "lowest_id": 2,
        "highest_id": 3,
        "events": [
            {
                "stream": "5020",
                "device_timestamp": None,
                "timestamp": "2018-01-20T00:00:00Z",
                "streamer_local_id": 2,
                "dirty_ts": False,
                "extra_data": {
                    "axis": "z",
                    "peak": 45.41939932879673,
                    "duration": 15,
                    "delta_v_x": 0.0,
                    "delta_v_y": 0.0,
                    "delta_v_z": 0.0
                }
            },
            {
                "stream": "5020",
                "device_timestamp": None,
                "timestamp": "2018-01-20T01:12:00Z",
                "streamer_local_id": 3,
                "dirty_ts": False,
                "extra_data": {
                    "axis": "z",
                    "peak": 58.13753330123034,
                    "duration": 15,
                    "delta_v_x": 0.0,
                    "delta_v_y": 0.0,
                    "delta_v_z": 0.0
                }
            }
        ]
    }

    encoded = msgpack.packb(data)
    decoded = msgpack.unpackb(encoded)
    report = FlexibleDictionaryReport(encoded, False, False)

    assert len(report.visible_readings) == 0
    assert len(report.visible_events) == 2

    ev1 = report.visible_events[0]
    ev2 = report.visible_events[1]

    assert isinstance(ev1.reading_time, datetime)
    assert isinstance(ev2.reading_time, datetime)

    assert ev1.summary_data == {
        "axis": "z",
        "peak": 45.41939932879673,
        "duration": 15,
        "delta_v_x": 0.0,
        "delta_v_y": 0.0,
        "delta_v_z": 0.0
    }

    assert ev2.summary_data == {
        "axis": "z",
        "peak": 58.13753330123034,
        "duration": 15,
        "delta_v_x": 0.0,
        "delta_v_y": 0.0,
        "delta_v_z": 0.0
    }
