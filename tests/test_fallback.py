from common.commands import Command
from common.errors import ErrorCode
from remote.button_emulation import Fallback


def test_tune_holds_400_ms():
    box = Fallback(initial_auto=False, initial_bypass=False)
    assert box.press_for(Command.TUN) == [("tune", 400)]


def test_reset_holds_tune_100_ms():
    box = Fallback()
    assert box.press_for(Command.RST) == [("tune", 100)]


def test_auto_press_toggles_once():
    box = Fallback()
    assert box.press_for(Command.AM0) == [("auto", 80)]
    assert box.auto is True
    assert box.press_for(Command.AM0) == []
    assert box.press_for(Command.AM1) == [("auto", 80)]
    assert box.auto is False


def test_bypass_press_turns_on():
    box = Fallback()
    assert box.press_for(Command.BYP1) == [("bypass", 80)]
    assert box.bypass is True


def test_direct_steps_are_data_not_available():
    box = Fallback()
    for command in (Command.TUP, Command.TDN, Command.TSC, Command.TSL, Command.TST0, Command.TST1):
        assert box.press_for(command) is ErrorCode.DATA_NOT_AVAILABLE


def test_status_is_data_not_available_in_fallback():
    box = Fallback()
    assert box.press_for(Command.STA) is ErrorCode.DATA_NOT_AVAILABLE
