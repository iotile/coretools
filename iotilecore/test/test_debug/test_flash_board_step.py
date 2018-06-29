from iotile.core.hw.debug.flash_board_step import FlashBoardStep
from iotile.core.exceptions import ArgumentError

import pytest

def test_flash_board_step():
    #Empty args
    with pytest.raises(ArgumentError):
          step = FlashBoardStep({})

    correct_args = {
        'file': 'test_file',
        'debug_string': 'device=nrf52'
    }
    step = FlashBoardStep(correct_args)
    assert step.FILES == [u'file']
    assert step.REQUIRED_RESOURCES == [(u'connection', u'hardware_manager')]
