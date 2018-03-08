import pytest
import os
from array import array
from iotile.core.hw.debug import DebugManager
from iotile.core.exceptions import ArgumentError

def test_process_hex():
    test_hexfile_name = os.path.join(os.path.dirname(__file__),"test_hexfile.hex")

    section_break_starts, section_data = DebugManager._process_hex(test_hexfile_name)

    print(section_break_starts)
    print(section_data)

    assert section_break_starts == [0x78000, 0x10001014]
    assert section_data[0] == array('B',[0,0,1,32,201,151,7,0,241,151,7,0,243,151,7,0])
    assert section_data[1] == array('B',[0,128,7,0])
