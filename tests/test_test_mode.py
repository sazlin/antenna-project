from common.commands import Command
from remote.atu_link import TestMode


def test_tst1_enters_test_mode_without_json():
    mode = TestMode()
    assert mode.command(Command.TST1) is None
    assert mode.active is True
    assert mode.step == 0


def test_tup_from_zero_sends_relay_i_1():
    mode = TestMode()
    mode.command(Command.TST1)
    assert mode.command(Command.TUP) == b'{"RelayI":1}\n'


def test_second_tup_sends_relay_i_2():
    mode = TestMode()
    mode.command(Command.TST1)
    mode.command(Command.TUP)
    assert mode.command(Command.TUP) == b'{"RelayI":2}\n'


def test_tdn_at_zero_sends_relay_i_0():
    mode = TestMode()
    mode.command(Command.TST1)
    assert mode.command(Command.TDN) == b'{"RelayI":0}\n'
    assert mode.step == 0


def test_inductor_ceiling_stays_127():
    mode = TestMode(inductor_count=7)
    mode.command(Command.TST1)
    for _ in range(127):
        mode.command(Command.TUP)
    assert mode.step == 127
    assert mode.command(Command.TUP) == b'{"RelayI":127}\n'


def test_tst0_sends_reset():
    mode = TestMode()
    mode.command(Command.TST1)
    assert mode.command(Command.TST0) == b'{"Reset":true}\n'
    assert mode.active is False


def test_tsc_from_step_1_sends_relay_c_130():
    mode = TestMode()
    mode.command(Command.TST1)
    mode.command(Command.TUP)
    assert mode.step == 1
    mode.command(Command.TSC)
    assert mode.step == 1
    assert mode.command(Command.TUP) == b'{"RelayC":130}\n'
