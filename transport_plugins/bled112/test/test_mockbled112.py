import unittest
from util.mock_bled112 import BGAPIPacket, MockBLED112

def test_create_disconnect_packet():
    """Verify that we can create and then parse a disconnect command
    """
    info = {
        'type': [3, 0, False, False],
        'handle': 1
    }

    packet = BGAPIPacket.GeneratePacket(info)
    parsed = BGAPIPacket(packet, False)

    assert parsed.event == False
    assert parsed.cmdclass == 3
    assert parsed.cmd == 0
    assert isinstance(parsed.payload, dict)
    assert parsed.payload['handle'] == 1

def test_create_disconnect_event():
    info = {
        'type': [3, 4, True, True],
        'handle': 1,
        'reason': 0x23E
    }

    packet = BGAPIPacket.GeneratePacket(info)
    parsed = BGAPIPacket(packet, True)

    assert parsed.event == True
    assert parsed.cmdclass == 3
    assert parsed.cmd == 4
    assert parsed.payload['handle'] == info['handle']
    assert parsed.payload['reason'] == info['reason']
