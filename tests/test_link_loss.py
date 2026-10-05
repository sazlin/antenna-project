from common.display import publish, render_banner, screen_lines
from common.state import LinkState
from master.tasks import on_link_lost as master_lost
from remote.tasks import on_link_lost as remote_lost


class _Latch:
    def __init__(self, value: int) -> None:
        self.value = value
        self.writes: list[int] = []

    def write(self, value: int) -> None:
        self.writes.append(value)


class _Panel:
    def __init__(self) -> None:
        self.lines = None

    def show_lines(self, lines: tuple[str, str, str, str]) -> None:
        self.lines = lines


def _reading_state() -> LinkState:
    return LinkState(
        forward_w=5.0,
        swr=1.15,
        inductance_nh=1250,
        capacitance_pf=150,
        auto=False,
        bypass=False,
        order="LC",
        efficiency_pct=None,
        antenna_w=None,
        link_up=True,
        banner="",
    )


def test_link_loss_keeps_antenna_three():
    remote = LinkState(antenna=3, relay_mask=0b0100)
    latch = _Latch(0b0100)
    remote_lost(remote, latch)
    assert remote.banner == "Communication Lost"
    assert remote.antenna == 3
    assert latch.writes == []
    master = LinkState()
    outbound: list[object] = []
    master_lost(master, outbound)
    assert master.banner == "Communication Lost"
    assert outbound == []


def test_communication_lost_banner_fits_the_panel():
    lines = render_banner("Communication Lost")
    assert lines == ("Communication", "Lost", "", "")
    assert all(len(line) <= 16 for line in lines)
    assert " ".join(line for line in lines if line) == "Communication Lost"
    state = _reading_state()
    remote_lost(state, _Latch(0))
    assert state.link_up is False
    panel = _Panel()
    publish(state, panel)
    assert panel.lines == lines
    clear = _reading_state()
    publish(clear, panel)
    assert panel.lines == screen_lines_for(clear)


def screen_lines_for(state: LinkState):
    from common.display import Reading

    return screen_lines(
        Reading(
            state.forward_w,
            state.swr,
            state.inductance_nh,
            state.capacitance_pf,
            state.auto,
            state.bypass,
            state.order,
            state.efficiency_pct,
            state.antenna_w,
        )
    )


def test_hot_switch_banner_shows_while_the_link_is_up():
    state = _reading_state()
    state.banner = "Hot switch"
    panel = _Panel()
    publish(state, panel)
    assert panel.lines == ("Hot switch", "", "", "")
    assert render_banner("Failed to Execute Command") == ("Failed to", "Execute Command", "", "")
    assert render_banner("Data Not Available") == ("Data Not", "Available", "", "")
    assert render_banner("Resource offline") == ("Resource offline", "", "", "")
    assert render_banner("Data Corrupted") == ("Data Corrupted", "", "", "")
    assert render_banner("Communication Lost") == ("Communication", "Lost", "", "")
