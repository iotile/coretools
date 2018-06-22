from iotile.core.hw.debug.flash_board_step import FlashBoardStep
from iotile.core.exceptions import ArgumentError

import pytest

def test_flash_board_step():
    #Empty args
    with pytest.raises(ArgumentError):
          step = FlashBoardStep({})

    correct_args = {
        'file': 'test_file',
        'port': 'jlink',
        'debug_string': 'device=nrf52'
    }
    step = FlashBoardStep(correct_args)
    assert step.FILES == [u'file']
    non_jlink_args = {
        'file': 'test_file',
        'port': 'bled112'
    }
    with pytest.raises(ArgumentError):
          step = FlashBoardStep(non_jlink_args)
