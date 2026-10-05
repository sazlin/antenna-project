from common.commands import Command
from common.menu import MASTER_MENU, REMOTE_MENU, Menu
from common.state import LinkState
from master.tasks import leds_for, master_on_press, write_leds
from remote.tasks import remote_on_press, write_leds as remote_write_leds


class _Olat:
    def __init__(self, port_a: int = 0, port_b: int = 0) -> None:
        self.port_a = port_a
        self.port_b = port_b


def test_tune_button_queues_tun():
    queue: list[Command] = []
    state = LinkState(antenna=1)
    menu = Menu(MASTER_MENU)
    master_on_press("tune", queue, state, menu)
    assert queue == [Command.TUN]
    queue.clear()
    master_on_press("antenna", queue, state, menu)
    assert queue == [Command.AT2]
    state.antenna = 4
    queue.clear()
    master_on_press("antenna", queue, state, menu)
    assert queue == [Command.AT1]
    assert Command.AT0 not in queue
    state.bypass = False
    queue.clear()
    master_on_press("bypass", queue, state, menu)
    assert queue == [Command.BYP1]
    state.bypass = True
    queue.clear()
    master_on_press("bypass", queue, state, menu)
    assert queue == [Command.BYP0]
    state.auto = False
    queue.clear()
    master_on_press("am", queue, state, menu)
    assert queue == [Command.AM0]
    state.auto = True
    queue.clear()
    master_on_press("am", queue, state, menu)
    assert queue == [Command.AM1]


def test_remote_select_queues_at1_while_link_is_down():
    menu = Menu(REMOTE_MENU, link_up=False)
    menu.open_menu()
    menu.right()
    local: list[str] = []
    remote_on_press("select", menu, local)
    assert local == ["at1"]


def test_leds_follow_the_state_flags():
    flags = leds_for(link_up=False, fault=True, auto=True, bypass=False, rf=True)
    assert flags == {
        "link_ok": False,
        "error": True,
        "auto": True,
        "bypass": False,
        "rf": True,
    }


def test_link_loss_sets_the_error_led_bit():
    from master.tasks import on_link_lost

    state = LinkState(link_up=True, auto=True, bypass=False, forward_w=1.1, antenna=1)
    olat = _Olat(port_b=0xFF)
    on_link_lost(state, [])
    write_leds(state, olat)
    assert olat.port_b & (1 << 2) == 0
    assert olat.port_b & (1 << 3)
    state.forward_w = 1.1
    state.link_up = True
    state.banner = ""
    write_leds(state, olat)
    assert olat.port_b & (1 << 6)
    state.forward_w = 1.0
    write_leds(state, olat)
    assert olat.port_b & (1 << 6) == 0
    state.auto = True
    state.bypass = False
    write_leds(state, olat)
    assert olat.port_b & (1 << 4)
    assert olat.port_b & (1 << 5) == 0
    remote = LinkState(link_up=False, banner="Communication Lost")
    remote_olat = _Olat(port_a=0, port_b=0b0101)
    remote_write_leds(remote, remote_olat)
    assert remote_olat.port_a & (1 << 5) == 0
    assert remote_olat.port_a & (1 << 6)
    assert remote_olat.port_b & 0x0F == 0b0101
