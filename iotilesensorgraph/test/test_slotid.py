import pytest

from iotile.sg import SlotIdentifier
from iotile.core.exceptions import ArgumentError

def test_slotid_parsing():
    """Make sure we can parse slot identifiers correctly."""

    slot_id = SlotIdentifier.FromString('slot 1')
    assert slot_id.address == 11

    slot_id = SlotIdentifier.FromString(u'slot 1')
    assert slot_id.address == 11

    slot_id = SlotIdentifier.FromString(u'slot 0x1')
    assert slot_id.address == 11

    slot_id = SlotIdentifier.FromString('controller')
    assert slot_id.address == 8

    slot_id = SlotIdentifier.FromString(u'controller')
    assert slot_id.address == 8

    with pytest.raises(ArgumentError):
        SlotIdentifier.FromString(u'asdf')

    with pytest.raises(ArgumentError):
        SlotIdentifier.FromString(u'controller 15')

    with pytest.raises(ArgumentError):
        SlotIdentifier.FromString(u'slot ab')

    slot1 = SlotIdentifier.FromString('slot 1')
    slot2 = SlotIdentifier.FromString('slot 1')
    con = SlotIdentifier.FromString('controller')

    assert slot1 == slot2
    assert not con == slot1
    assert con != slot1


def test_slotid_binary_parsing():
    """Make sure we can generate and parse binary descriptors."""

    slot_id = SlotIdentifier.FromString('slot 1')
    assert SlotIdentifier.FromEncoded(slot_id.encode()) == slot_id

    con = SlotIdentifier.FromString('controller')
    assert SlotIdentifier.FromEncoded(con.encode()) == con
