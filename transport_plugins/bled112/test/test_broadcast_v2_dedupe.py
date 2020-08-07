from unittest.mock import patch
from typing import List
from iotile_transport_bled112.broadcast_v2_dedupe import packet_is_broadcast_v2, BroadcastV2Deduper, BroadcastV2DeduperCollection
from iotile.cloud.utilities import device_id_to_slug

#pylint: disable=invalid-name,line-too-long


pod_9001 = [
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x01\x90\x00\x00\x00\x00\x00\x00\x897\x01\x00\xa0\x00@\x10\x00\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x01\x90\x00\x00\x00\x00\x00\x00\x897\x01\x00\xa0\x00@\x10\x01\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x01\x90\x00\x00\x00\x00\x00\x00\x8a7\x01\x00\xa0\x00@\x10\x02\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x01\x90\x00\x00\x00\x00\x00\x00\x8a7\x01\x00\xa0\x00@\x10\x03\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x01\x90\x00\x00\x00\x00\x00\x00\x8a7\x01\x00\xa0\x00@\x10\x04\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x01\x90\x00\x00\x00\x00\x00\x00\x8a7\x01\x00\xa0\x00@\x10\x05\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x01\x90\x00\x00\x00\x00\x00\x00\x8a7\x01\x00\xa0\x00@\x10\x06\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x01\x90\x00\x00\x00\x00\x00\x00\x8a7\x01\x00\xa0\x00@\x10\x07\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x01\x90\x00\x00\x00\x00\x00\x00\x8a7\x01\x00\xa0\x00@\x10\x08\x00\x00\x00\x00\x00\x00\x00'
]

pod_9002 = [
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x02\x90\x00\x00\x00\x00\x00\x00\x9f7\x01\x00\xa0\x00@\x10\x00\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x02\x90\x00\x00\x00\x00\x00\x00\x9f7\x01\x00\xa0\x00@\x10\x01\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x02\x90\x00\x00\x00\x00\x00\x00\x9f7\x01\x00\xa0\x00@\x10\x02\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x02\x90\x00\x00\x00\x00\x00\x00\x9f7\x01\x00\xa0\x00@\x10\x03\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x02\x90\x00\x00\x00\x00\x00\x00\x9f7\x01\x00\xa0\x00@\x10\x04\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x02\x90\x00\x00\x00\x00\x00\x00\xa07\x01\x00\xa0\x00@\x10\x05\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x02\x90\x00\x00\x00\x00\x00\x00\xa07\x01\x00\xa0\x00@\x10\x06\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x02\x90\x00\x00\x00\x00\x00\x00\xa07\x01\x00\xa0\x00@\x10\x07\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x02\x90\x00\x00\x00\x00\x00\x00\xa07\x01\x00\xa0\x00@\x10\x08\x00\x00\x00\x00\x00\x00\x00'
]

pod_9003 = [
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x03\x90\x00\x00\x00\x00\x00\x00\xb97\x01\x00\xa0\x00@\x10\x00\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x03\x90\x00\x00\x00\x00\x00\x00\xb97\x01\x00\xa0\x00@\x10\x01\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x03\x90\x00\x00\x00\x00\x00\x00\xb97\x01\x00\xa0\x00@\x10\x02\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x03\x90\x00\x00\x00\x00\x00\x00\xb97\x01\x00\xa0\x00@\x10\x03\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x03\x90\x00\x00\x00\x00\x00\x00\xb97\x01\x00\xa0\x00@\x10\x04\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x03\x90\x00\x00\x00\x00\x00\x00\xb97\x01\x00\xa0\x00@\x10\x05\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x03\x90\x00\x00\x00\x00\x00\x00\xb97\x01\x00\xa0\x00@\x10\x06\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x03\x90\x00\x00\x00\x00\x00\x00\xba7\x01\x00\xa0\x00@\x10\x07\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x03\x90\x00\x00\x00\x00\x00\x00\xba7\x01\x00\xa0\x00@\x10\x08\x00\x00\x00\x00\x00\x00\x00'
]

pod_9004 = [
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x04\x90\x00\x00\x00\x00\x00\x00\xce7\x01\x00\xa0\x00@\x10\x00\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x04\x90\x00\x00\x00\x00\x00\x00\xce7\x01\x00\xa0\x00@\x10\x01\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x04\x90\x00\x00\x00\x00\x00\x00\xce7\x01\x00\xa0\x00@\x10\x02\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x04\x90\x00\x00\x00\x00\x00\x00\xcf7\x01\x00\xa0\x00@\x10\x03\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x04\x90\x00\x00\x00\x00\x00\x00\xcf7\x01\x00\xa0\x00@\x10\x04\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x04\x90\x00\x00\x00\x00\x00\x00\xcf7\x01\x00\xa0\x00@\x10\x05\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x04\x90\x00\x00\x00\x00\x00\x00\xcf7\x01\x00\xa0\x00@\x10\x06\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x04\x90\x00\x00\x00\x00\x00\x00\xcf7\x01\x00\xa0\x00@\x10\x07\x00\x00\x00\x00\x00\x00\x00',
    b'\x02\x01\x06\x1b\x16\xdd\xfd\x04\x90\x00\x00\x00\x00\x00\x00\xcf7\x01\x00\xa0\x00@\x10\x08\x00\x00\x00\x00\x00\x00\x00'
]


bled_init_packets = [
    b'\x00\x01\x00\x06\x03',
    b'\x80\x10\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff',
    b'\x80\x10\x03\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff',
]

def load_pod(pod_data):
    output = []
    bluetooth_preamble = b'\x80\x2a\x06\x00\xca\x00\x00\x90\x29\x81\x25\xcb\x01\xff\x1f'
    for broadcast in pod_data:
        packet = bytearray(bluetooth_preamble)
        packet.extend(bytearray(broadcast))
        output.append(packet)
    return output

def test_single_deduper():
    pod = load_pod(pod_9001)
    assert len(pod[0]) == 46
    assert packet_is_broadcast_v2(pod[0])

    uuid = bytes(pod[0][22:26])
    deduper = BroadcastV2Deduper(uuid)
    assert deduper.get_slug() == "d--0000-0000-0000-9001"

    assert deduper.allow_packet(pod[0][22:])
    assert deduper.last_data == pod[0][22:]

    assert not deduper.allow_packet(pod[0][22:])
    assert not deduper.allow_packet(pod[0][22:])
    assert deduper.allow_packet(pod[1][22:])

def test_collection_one_pod():
    pod = load_pod(pod_9001)

    dedupers = BroadcastV2DeduperCollection()
    assert dedupers.allow_packet(pod[0])
    assert len(dedupers.dedupers) == 1

    assert not dedupers.allow_packet(pod[0])
    assert len(dedupers.dedupers) == 1

    assert not dedupers.allow_packet(pod[0])
    assert not dedupers.allow_packet(pod[0])
    assert dedupers.allow_packet(pod[1])
    assert dedupers.allow_packet(pod[2])
    assert not dedupers.allow_packet(pod[2])
    assert not dedupers.allow_packet(pod[2])
    assert dedupers.allow_packet(pod[3])

def test_non_broadcast_packets():
    pod = load_pod(pod_9001)

    dedupers = BroadcastV2DeduperCollection()
    assert dedupers.allow_packet(bled_init_packets[0])
    assert dedupers.allow_packet(pod[0])
    assert dedupers.allow_packet(pod[1])
    assert dedupers.allow_packet(bled_init_packets[0])
    assert dedupers.allow_packet(bled_init_packets[0])
    assert dedupers.allow_packet(bled_init_packets[1])
    assert not dedupers.allow_packet(pod[1])
    assert dedupers.allow_packet(bled_init_packets[2])

def test_collection_four_pods():
    dedupers = BroadcastV2DeduperCollection()

    pod1 = load_pod(pod_9001)
    pod2 = load_pod(pod_9002)
    pod3 = load_pod(pod_9003)
    pod4 = load_pod(pod_9004)

    # First three come up
    assert dedupers.allow_packet(pod1[0])
    assert dedupers.allow_packet(pod2[0])
    assert dedupers.allow_packet(pod3[0])

    # Some Duplicates from first three, followed by new ones from 1 and 2
    assert not dedupers.allow_packet(pod1[0])
    assert not dedupers.allow_packet(pod2[0])
    assert not dedupers.allow_packet(pod1[0])
    assert not dedupers.allow_packet(pod2[0])
    assert not dedupers.allow_packet(pod3[0])
    assert not dedupers.allow_packet(pod3[0])
    assert dedupers.allow_packet(pod1[1])
    assert dedupers.allow_packet(pod2[1])

    # 4 comes up, has a burst of dupes
    assert dedupers.allow_packet(pod4[0])
    assert not dedupers.allow_packet(pod4[0])
    assert not dedupers.allow_packet(pod4[0])
    assert not dedupers.allow_packet(pod4[0])
    assert not dedupers.allow_packet(pod4[0])

    # 2 rapidly increases, nothing else chatters
    assert dedupers.allow_packet(pod2[2])
    assert dedupers.allow_packet(pod2[3])
    assert dedupers.allow_packet(pod2[4])
    assert dedupers.allow_packet(pod2[5])
    assert dedupers.allow_packet(pod2[6])

    # 3 rapidly increases, while 1 occasionally increases and 2 stays the same
    assert dedupers.allow_packet(pod3[2])
    assert dedupers.allow_packet(pod3[3])
    assert not dedupers.allow_packet(pod2[6])
    assert dedupers.allow_packet(pod1[2])
    assert not dedupers.allow_packet(pod1[2])
    assert not dedupers.allow_packet(pod2[6])
    assert dedupers.allow_packet(pod3[4])
    assert not dedupers.allow_packet(pod1[2])
    assert dedupers.allow_packet(pod3[5])
    assert dedupers.allow_packet(pod3[6])
    assert not dedupers.allow_packet(pod2[6])
    assert dedupers.allow_packet(pod1[3])

def test_timeout():
    with patch('iotile_transport_bled112.broadcast_v2_dedupe.time.monotonic', return_value=1):
        dedupers = BroadcastV2DeduperCollection(pass_packets_every=5)

        pod1 = load_pod(pod_9001)
        pod2 = load_pod(pod_9002)

        # First two come up
        assert dedupers.allow_packet(pod1[0])
        assert dedupers.allow_packet(pod2[0])

    with patch('iotile_transport_bled112.broadcast_v2_dedupe.time.monotonic', return_value=3):
        # 1 changes, 2 doesn't, we're not before packets should be passed
        assert dedupers.allow_packet(pod1[1])
        assert not dedupers.allow_packet(pod2[0])

    with patch('iotile_transport_bled112.broadcast_v2_dedupe.time.monotonic', return_value=7):
        # both stay the same,  But 2 should be allowed because it's been 6 seconds
        assert not dedupers.allow_packet(pod1[1])
        assert dedupers.allow_packet(pod2[0])

    with patch('iotile_transport_bled112.broadcast_v2_dedupe.time.monotonic', return_value=20):
        # both stay the same, allow both, it's past the timeout 
        assert dedupers.allow_packet(pod1[1])
        assert dedupers.allow_packet(pod2[0])

    with patch('iotile_transport_bled112.broadcast_v2_dedupe.time.monotonic', return_value=21):
        # both stay the same, but it's only been a second since the last so deny
        assert not dedupers.allow_packet(pod1[1])
        assert not dedupers.allow_packet(pod2[0])

    with patch('iotile_transport_bled112.broadcast_v2_dedupe.time.monotonic', return_value=22):
        # They both change, let them through
        assert dedupers.allow_packet(pod1[2])
        assert dedupers.allow_packet(pod2[1])


def assert_pods_in_dedupercollection(uuids: List[int], dedupercollection: BroadcastV2DeduperCollection):
    deduper_slugs = []  #type: List[str]
    for deduper in iter(dedupercollection.dedupers.values()):
        deduper_slugs.append(deduper.get_slug())

    for uuid in uuids:
        assert device_id_to_slug(uuid) in deduper_slugs

def test_eviction():
    dedupers = BroadcastV2DeduperCollection()
    dedupers.MAX_DEDUPERS = 3

    pod1 = load_pod(pod_9001)
    pod2 = load_pod(pod_9002)
    pod3 = load_pod(pod_9003)
    pod4 = load_pod(pod_9004)

    # First three come up
    with patch('iotile_transport_bled112.broadcast_v2_dedupe.time.monotonic', return_value=1):
        assert dedupers.allow_packet(pod1[0])
    with patch('iotile_transport_bled112.broadcast_v2_dedupe.time.monotonic', return_value=2):
        assert dedupers.allow_packet(pod2[0])
    with patch('iotile_transport_bled112.broadcast_v2_dedupe.time.monotonic', return_value=3):
        assert dedupers.allow_packet(pod3[0])

    #Fourth comes up, Pod1 should be evicted

    with patch('iotile_transport_bled112.broadcast_v2_dedupe.time.monotonic', return_value=4):
        assert dedupers.allow_packet(pod4[0])
    assert len(dedupers.dedupers) == dedupers.MAX_DEDUPERS
    assert_pods_in_dedupercollection([0x9002, 0x9003, 0x9004], dedupers)

