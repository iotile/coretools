from builtins import range
import pytest
from iotile.core.hw.debug import SparseMemory
from iotile.core.exceptions import ArgumentError


@pytest.fixture(scope='function')
def single_segment():
    mem = SparseMemory()
    mem.add_segment(0, bytearray(range(0, 256)))
    return mem


@pytest.fixture
def multi_segment(scope='function'):
    mem = SparseMemory()
    mem.add_segment(0, bytearray(range(0, 256)))
    mem.add_segment(8192, bytearray(range(0, 256)))
    return mem


def test_sparsememory_basicusage():
    """Make sure we can create a SparseMemory and use it
    """

    mem = SparseMemory()
    mem.add_segment(0x1000, bytearray(4096))

    # Make sure slice and basic access work
    assert mem[0x1000] == 0

    dataslice = mem[0x1000:0x1400]
    assert len(dataslice) == 0x400

    # Make sure we can't access data we don't have
    with pytest.raises(ArgumentError):
        mem[0x900]

    with pytest.raises(ArgumentError):
        mem[0x2000]

    with pytest.raises(ArgumentError):
        mem[0x800:0x1200]

    with pytest.raises(ArgumentError):
        mem[0x1000:0x1200:2]

def test_getitem_multisegment(multi_segment):
    mem = multi_segment

    assert mem[255] == 255
    assert mem[8192] == 0
    assert mem[8193] == 1

def test_setitem_multisegment(multi_segment):
    mem = multi_segment

    mem[255] = 5
    assert mem[255] == 5

    mem[8192:8194] = (5, 10)
    assert mem[8192] == 5
    assert mem[8193] == 10

def test_stringify(single_segment):
    mem = single_segment

    lines = str(mem).rstrip().split('\n')
    assert len(lines) == 16
    assert len(lines[0]) == 78

def test_multistringify(multi_segment):
    mem = multi_segment

    print(str(mem))
