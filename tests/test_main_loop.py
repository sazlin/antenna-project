from common.commands import Command
from common.display import Reading, screen_lines
from common.hal import note_rx_byte
from common.protocol import Frame, decode_frames, encode_frame
from common.scheduler import run_once
from master.tasks import MasterApp, build_master_tasks
from remote.tasks import PowerView, RemoteApp, build_remote_tasks


def _load(ring, flags, data: bytes) -> None:
    for byte in data:
        note_rx_byte(ring, flags, byte)


def _run(tasks, feeds: list[int]) -> None:
    run_once(tasks, interrupt=lambda: None, watchdog=lambda: feeds.append(1))


def test_master_pass_polls_when_the_clock_reaches_poll_ms():
    from common import hal
    from master.main import run_production_pass

    app = MasterApp()
    app.tasks = build_master_tasks(app)
    hal.set_host_ticks_ms(0)
    try:
        run_production_pass(app)
        assert app.tx == b""
        hal.set_host_ticks_ms(200)
        run_production_pass(app)
        frames, leftover = decode_frames(bytes(app.tx))
        assert leftover == b""
        assert frames[0].command is Command.HHH
        assert frames[0].sequence != 0
    finally:
        hal.set_host_ticks_ms(0)


def test_remote_run_once_drains_and_feeds():
    app = RemoteApp()
    app.power = PowerView(0.2, 0, 0)
    app.presses.append("up")
    _load(app.rs485, app.rs485_flags, encode_frame(Frame(1, 2, 1, Command.AT2, b"")))
    feeds: list[int] = []
    _run(build_remote_tasks(app), feeds)
    assert app.latch.read() == 0b0010
    assert app.atu_polls == 1
    assert app.publishes == 1
    assert app.events == ["up"]
    assert feeds == [1]


def test_master_run_once_drains_and_feeds():
    app = MasterApp()
    app.now_ms = 200
    _load(
        app.rs485,
        app.rs485_flags,
        encode_frame(Frame(2, 1, 1, Command.ACK, bytes([Command.HHH.byte]))),
    )
    app.presses.append("up")
    feeds: list[int] = []
    _run(build_master_tasks(app), feeds)
    assert app.publishes == 1
    assert app.events == ["up"]
    assert feeds == [1]


def test_idle_poll_loss_does_not_move_relays():
    import remote.relays as relays

    app = MasterApp()
    app.now_ms = 200
    _run(build_master_tasks(app), [])
    app.link._pending.tries = app.link.reply_tries
    app.link._pending.sent_ms = 0
    app.link.misses = 4
    app.now_ms = 500
    calls = {"set": 0, "off": 0}
    original_set = relays.set_antenna
    original_off = relays.force_all_off

    def _set(*_args, **_kwargs):
        calls["set"] += 1

    def _off(*_args, **_kwargs):
        calls["off"] += 1

    relays.set_antenna = _set
    relays.force_all_off = _off
    try:
        _run(build_master_tasks(app), [])
    finally:
        relays.set_antenna = original_set
        relays.force_all_off = original_off
    assert app.link.link_lost is True
    assert app.state.banner == "Communication Lost"
    assert calls == {"set": 0, "off": 0}


def test_queued_at2_is_sent_instead_of_hhh():
    idle = MasterApp()
    idle.now_ms = 200
    _run(build_master_tasks(idle), [])
    assert decode_frames(bytes(idle.tx))[0][0].command is Command.HHH
    app = MasterApp()
    app.now_ms = 200
    app.link.enqueue(Command.AT2)
    _run(build_master_tasks(app), [])
    sent = decode_frames(bytes(app.tx))[0][0]
    assert sent.command is Command.AT2
    _load(
        app.rs485,
        app.rs485_flags,
        encode_frame(Frame(2, 1, sent.sequence, Command.ACK, bytes([Command.AT2.byte]))),
    )
    app.now_ms = 400
    _run(build_master_tasks(app), [])
    frames, _leftover = decode_frames(bytes(app.tx))
    assert frames[-1].command is Command.HHH


def test_remote_silence_sets_communication_lost():
    app = RemoteApp()
    app.state.antenna = 3
    app.latch.value = 0b0100
    app.last_accept_ms = 0
    app.now_ms = 1999
    _run(build_remote_tasks(app), [])
    assert app.state.antenna == 3
    assert app.latch.writes == []
    assert app.state.banner == ""
    app.now_ms = 2000
    _run(build_remote_tasks(app), [])
    assert app.state.banner == "Communication Lost"
    assert app.latch.value == 0b0100
    _load(app.rs485, app.rs485_flags, encode_frame(Frame(1, 2, 3, Command.HHH, b"")))
    app.now_ms = 2100
    _run(build_remote_tasks(app), [])
    assert app.state.banner == ""
    assert app.state.link_up is True


def _pump(master: MasterApp, remote: RemoteApp) -> None:
    _run(build_master_tasks(master), [])
    if master.tx:
        _load(remote.rs485, remote.rs485_flags, bytes(master.tx))
        master.tx.clear()
    _run(build_remote_tasks(remote), [])
    if remote.tx:
        _load(master.rs485, master.rs485_flags, bytes(remote.tx))
        remote.tx.clear()
    master.shared["antenna_w"] = remote.shared.get("antenna_w")
    _run(build_master_tasks(master), [])


def _status_case(body: bytes, order: str, bit6: int, expected: tuple[str, str, str, str]) -> None:
    remote = RemoteApp()
    master = MasterApp()
    master.shared = remote.shared
    remote.now_ms = 1000
    master.now_ms = 1000
    _load(remote.atu_ring, remote.atu_flags, body)
    _run(build_remote_tasks(remote), [])
    assert remote.state.order == order
    assert remote.state.power_sample_ms == 1000
    assert len(remote.link._pending_status) == 13
    assert (remote.link._pending_status[0] & 0x40) == bit6
    for tick in (1200, 1400, 1600, 1800):
        remote.now_ms = tick
        master.now_ms = tick
        _pump(master, remote)
    state = master.state
    lines = screen_lines(
        Reading(
            state.forward_w or 0,
            state.swr or 0,
            state.inductance_nh or 0,
            state.capacitance_pf or 0,
            state.auto,
            state.bypass,
            state.order or "LC",
            state.efficiency_pct,
            state.antenna_w,
        )
    )
    assert state.order == order
    assert lines == expected


def test_atu_status_is_committed_and_sent():
    tuned = (
        "{\n"
        '  "Auto": true,\n'
        '  "Bypass": false,\n'
        '  "efficency": 90,\n'
        '  "Power": 9.0,\n'
        '  "Forward": 10.0,\n'
        '  "SWR": 1.10,\n'
        '  "Order": "LC"\n'
        "}\n"
    )
    screen = ("10.0W          .", "1.10", "9.0W", "90%")
    _status_case(tuned.encode(), "LC", 0, screen)
    _status_case(tuned.replace('"LC"', '"CL"').encode(), "CL", 0x40, screen)
    inductors = (
        "{\n"
        '  "Forward": 10.0,\n'
        '  "SWR": 1.10,\n'
        '  "Inductance": 1250,\n'
        '  "Capacitance": 150,\n'
        '  "Order": "CL"\n'
        "}\n"
    )
    _status_case(inductors.encode(), "CL", 0x40, ("10.0W           ", "1.10", "150pF", "1.25uH"))
    _status_case(
        inductors.replace('"CL"', '"LC"').encode(),
        "LC",
        0,
        ("10.0W           ", "1.10", "1.25uH", "150pF"),
    )
