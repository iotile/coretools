from iotile.core.hw.debug.flash_board_step import FlashBoardStep

def test_flash_board_step():
    args = {
        'file': 'test_file',
        'port': 'jlink:device=nrf52;serial=50000797'
    }
    step = FlashBoardStep(args)