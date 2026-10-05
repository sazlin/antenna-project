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


def test_ack_clears_communication_lost_and_stale_power_drops_rf_present():
    from master.tasks import write_leds

    app = MasterApp()
    app.now_ms = 200
    _run(build_master_tasks(app), [])
    sent = decode_frames(bytes(app.tx))[0][0]
    app.tx.clear()
    app.link.link_lost = True
    app.state.banner = "Communication Lost"
    app.state.link_up = False
    _load(
        app.rs485,
        app.rs485_flags,
        encode_frame(Frame(2, 1, sent.sequence, Command.ACK, bytes([Command.HHH.byte]))),
    )
    _run(build_master_tasks(app), [])
    assert app.state.banner == ""
    assert app.state.link_up is True
    assert app.olat.port_b & (1 << 2)
    assert app.olat.port_b & (1 << 3) == 0
    assert app.link._queue == []

    hot = MasterApp()
    hot.now_ms = 200
    _run(build_master_tasks(hot), [])
    hot_sent = decode_frames(bytes(hot.tx))[0][0]
    hot.state.banner = "Hot switch"
    hot.state.link_up = True
    _load(
        hot.rs485,
        hot.rs485_flags,
        encode_frame(Frame(2, 1, hot_sent.sequence, Command.ACK, bytes([Command.HHH.byte]))),
    )
    _run(build_master_tasks(hot), [])
    assert hot.state.banner == "Hot switch"

    stale = MasterApp()
    stale.state.forward_w = 1.1
    stale.state.power_sample_ms = 0
    stale.now_ms = 1000
    write_leds(stale.state, stale.olat, stale.now_ms)
    assert stale.olat.port_b & (1 << 6) == 0
    stale.state.power_sample_ms = stale.now_ms
    write_leds(stale.state, stale.olat, stale.now_ms)
    assert stale.olat.port_b & (1 << 6)
    stale.state.forward_w = 1.0
    write_leds(stale.state, stale.olat, stale.now_ms)
    assert stale.olat.port_b & (1 << 6) == 0


def test_mcp_gpio_press_enqueues_tune():
    from master.main import _interrupt as master_interrupt
    from remote.main import _interrupt as remote_interrupt

    class Chip:
        def __init__(self) -> None:
            self.levels = (0xFF, 0xFF)

        def read_gpio(self) -> tuple[int, int]:
            return self.levels

    def one_pass(app, interrupt) -> None:
        run_once(app.tasks, interrupt=lambda: interrupt(app), watchdog=lambda: None)

    master = MasterApp()
    master.tasks = build_master_tasks(master)
    chip = Chip()
    master.mcp = chip
    chip.levels = (0xFF & ~(1 << 5), 0xFF)
    master.mcp_flag.mcp = True
    master.now_ms = 1000
    one_pass(master, master_interrupt)
    chip.levels = (0xFF, 0xFF)
    master.mcp_flag.mcp = True
    master.now_ms = 1030
    one_pass(master, master_interrupt)
    assert [item[0] for item in master.link._queue] == [Command.TUN]

    short = MasterApp()
    short.tasks = build_master_tasks(short)
    short_chip = Chip()
    short.mcp = short_chip
    short_chip.levels = (0xFF & ~(1 << 5), 0xFF)
    short.mcp_flag.mcp = True
    short.now_ms = 0
    one_pass(short, master_interrupt)
    short_chip.levels = (0xFF, 0xFF)
    short.mcp_flag.mcp = True
    short.now_ms = 29
    one_pass(short, master_interrupt)
    assert short.link._queue == []

    remote = RemoteApp()
    remote.tasks = build_remote_tasks(remote)
    remote.state.link_up = False
    remote.menu.open_menu()
    remote.menu.right()
    assert remote.menu.label == "Antenna 1"
    remote_chip = Chip()
    remote.mcp = remote_chip
    remote_chip.levels = (0xFF & ~(1 << 4), 0xFF)
    remote.mcp_flag.mcp = True
    remote.now_ms = 2000
    one_pass(remote, remote_interrupt)
    remote_chip.levels = (0xFF, 0xFF)
    remote.mcp_flag.mcp = True
    remote.now_ms = 2030
    one_pass(remote, remote_interrupt)
    assert remote.latch.read() == 0b0001
    assert remote.tx == b""


def test_menu_select_enqueues_at1_on_the_master_link():
    from master.tasks import _master_buttons

    def tap(app, name: str, at: int) -> None:
        app.held[name] = True
        app.now_ms = at
        _master_buttons(app)
        app.now_ms = at + 30
        _master_buttons(app)
        app.held[name] = False
        app.now_ms = at + 31
        _master_buttons(app)

    app = MasterApp()
    app.state.forward_w = 5.0
    app.state.swr = 1.1
    app.state.inductance_nh = 1250
    app.state.capacitance_pf = 150
    app.state.order = "LC"
    tap(app, "Menu", 0)
    assert app.menu.active is True
    tap(app, "Right", 100)
    assert app.menu.label == "Antenna 1"
    _master_publish = __import__("master.tasks", fromlist=["_master_publish"])._master_publish
    _master_publish(app)
    labels = [line for line in app.panel.lines if line]
    assert len(labels) <= 4
    assert app.panel.lines[app.menu_highlight] == "Antenna 1"
    tap(app, "Select", 200)
    assert app.menu.active is False
    app.now_ms = 400
    _run(build_master_tasks(app), [])
    sent = decode_frames(bytes(app.tx))[0][0]
    assert sent.command is Command.AT1
    _master_publish(app)
    assert app.panel.lines[1] == "1.10"

    closed = MasterApp()
    tap_exit = tap
    tap_exit(closed, "Menu", 0)
    tap_exit(closed, "Up", 100)
    assert closed.menu.label == "Exit Menu"
    tap_exit(closed, "Select", 200)
    assert closed.link._queue == []
    shutdown = MasterApp()
    tap(shutdown, "Menu", 0)
    tap(shutdown, "Down", 40)
    tap(shutdown, "Down", 80)
    assert shutdown.menu.label == "Shutdown"
    tap(shutdown, "Select", 120)
    assert [item[0] for item in shutdown.link._queue] == [Command.F86]

    from remote.tasks import _remote_buttons

    def tap_remote(board, name: str, at: int) -> None:
        board.held[name] = True
        board.now_ms = at
        _remote_buttons(board)
        board.now_ms = at + 30
        _remote_buttons(board)
        board.held[name] = False
        board.now_ms = at + 31
        _remote_buttons(board)

    remote = RemoteApp()
    remote.state.link_up = False
    tap_remote(remote, "Menu", 0)
    tap_remote(remote, "Right", 100)
    tap_remote(remote, "Down", 200)
    tap_remote(remote, "Down", 300)
    tap_remote(remote, "Down", 400)
    assert remote.menu.label == "Antenna 4"
    tap_remote(remote, "Select", 500)
    assert remote.latch.read() == 0b1000
    assert remote.tx == b""
    stepper = RemoteApp()

    def choose_step_up(board, base: int) -> None:
        tap_remote(board, "Menu", base)
        tap_remote(board, "Down", base + 40)
        tap_remote(board, "Right", base + 80)
        for step in range(7):
            tap_remote(board, "Down", base + 120 + step)
        assert board.menu.label == "Step up"
        tap_remote(board, "Select", base + 200)

    choose_step_up(stepper, 0)
    choose_step_up(stepper, 1000)
    assert stepper.port_writes == [b'{"RelayI":1}\n', b'{"RelayI":2}\n']


def test_production_loop_feeds_the_watchdog_each_pass():
    from common import hal
    from master.main import boot_devices, run_production_pass

    feeds: list[int] = []

    class Watchdog:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        def feed(self) -> None:
            feeds.append(1)

    class Machine:
        def WDT(self, timeout: int) -> Watchdog:
            return Watchdog(timeout)

        def Pin(self, number, *args, **kwargs):
            return number

        def UART(self, uart_id, baudrate=None, tx=None, rx=None, **kwargs):
            return type("U", (), {"id": uart_id})()

        def I2C(self, i2c_id, scl, sda, freq=400000):
            class Bus:
                def writeto_mem(self, addr, reg, buf):
                    return None

                def readfrom_mem(self, addr, reg, nbytes):
                    return bytes(nbytes)

                def writeto(self, addr, buf):
                    return None

            return Bus()

    hal.bind(Machine())
    try:
        board = boot_devices("master")
        assert hal.watchdog_ms == 3000
        run_production_pass(board)
        assert feeds == [1]
        assert "machine" not in __import__("sys").modules
    finally:
        hal.bind(None)
        hal.start_watchdog(3000)


def test_live_antenna_change_waits_relay_delay_ms():
    import pytest

    from common import hal
    from common.errors import RelayFault
    from remote.relays import set_antenna

    slept: list[int] = []
    hal.set_sleep_hook(slept.append)
    try:
        app = RemoteApp()
        _load(app.rs485, app.rs485_flags, encode_frame(Frame(1, 2, 1, Command.AT2, b"")))
        _run(build_remote_tasks(app), [])
        assert slept == [100]
        slept.clear()
        _load(app.rs485, app.rs485_flags, encode_frame(Frame(1, 2, 2, Command.AT2, b"")))
        _run(build_remote_tasks(app), [])
        assert slept == []

        class TwoBit:
            def read(self) -> int:
                return 0b0101

            def write(self, value: int) -> None:
                self.value = value

        with pytest.raises(RelayFault):
            set_antenna(TwoBit(), 3, delay_ms=100, sleep=hal.sleep_ms)
        assert slept == []
    finally:
        hal.set_sleep_hook(lambda _delay_ms: None)


def _forward_status(watts: float) -> bytes:
    return (
        "{\n"
        f'  "Forward": {watts:.1f},\n'
        '  "SWR": 1.10\n'
        "}\n"
    ).encode()


def test_committed_forward_power_blocks_the_next_antenna_command():
    blocked = RemoteApp()
    blocked.now_ms = 1000
    _load(blocked.atu_ring, blocked.atu_flags, _forward_status(5.0))
    _run(build_remote_tasks(blocked), [])
    assert blocked.state.forward_w == 5.0
    _load(blocked.rs485, blocked.rs485_flags, encode_frame(Frame(1, 2, 2, Command.AT2, b"")))
    _run(build_remote_tasks(blocked), [])
    assert blocked.latch.read() == 0
    err = decode_frames(bytes(blocked.tx))[0][0]
    assert err.command is Command.ERR
    assert err.payload == bytes([6, 2, 0x12])

    allowed = RemoteApp()
    allowed.now_ms = 1000
    _load(allowed.atu_ring, allowed.atu_flags, _forward_status(1.0))
    _run(build_remote_tasks(allowed), [])
    _load(allowed.rs485, allowed.rs485_flags, encode_frame(Frame(1, 2, 2, Command.AT2, b"")))
    _run(build_remote_tasks(allowed), [])
    assert allowed.latch.read() == 0b0010
    ack = decode_frames(bytes(allowed.tx))[0][0]
    assert ack.command is Command.ACK
    assert ack.payload == bytes([0x12])

    shutdown = RemoteApp()
    shutdown.latch.value = 0b0010
    shutdown.state.antenna = 2
    shutdown.state.relay_mask = 0b0010
    shutdown.now_ms = 1000
    _load(shutdown.atu_ring, shutdown.atu_flags, _forward_status(50.0))
    _run(build_remote_tasks(shutdown), [])
    _load(shutdown.rs485, shutdown.rs485_flags, encode_frame(Frame(1, 2, 3, Command.F86, b"")))
    _run(build_remote_tasks(shutdown), [])
    assert shutdown.latch.read() == 0


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


def test_master_efficiency_screen_comes_from_the_snd_payload():
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
    ).encode()
    remote = RemoteApp()
    master = MasterApp()
    remote.now_ms = 1000
    master.now_ms = 1000
    _load(remote.atu_ring, remote.atu_flags, tuned)
    _run(build_remote_tasks(remote), [])

    def move() -> None:
        _run(build_master_tasks(master), [])
        if master.tx:
            _load(remote.rs485, remote.rs485_flags, bytes(master.tx))
            master.tx.clear()
        _run(build_remote_tasks(remote), [])
        if remote.tx:
            _load(master.rs485, master.rs485_flags, bytes(remote.tx))
            remote.tx.clear()
        _run(build_master_tasks(master), [])

    for tick in (1200, 1400, 1600, 1800):
        remote.now_ms = tick
        master.now_ms = tick
        move()
    assert master.shared.get("antenna_w") is None or "antenna_w" not in master.shared
    state = master.state
    lines = screen_lines(
        Reading(
            state.forward_w or 0,
            state.swr or 0,
            state.inductance_nh or 0,
            state.capacitance_pf or 0,
            bool(state.auto),
            bool(state.bypass),
            state.order or "LC",
            state.efficiency_pct,
            state.antenna_w,
        )
    )
    assert lines == ("10.0W          .", "1.10", "9.0W", "90%")
    bare = (
        "{\n"
        '  "Forward": 10.0,\n'
        '  "SWR": 1.10,\n'
        '  "Inductance": 1250,\n'
        '  "Capacitance": 150,\n'
        '  "Order": "CL"\n'
        "}\n"
    ).encode()
    _status_case(bare, "CL", 0x40, ("10.0W           ", "1.10", "150pF", "1.25uH"))


def _pump(master: MasterApp, remote: RemoteApp) -> None:
    _run(build_master_tasks(master), [])
    if master.tx:
        _load(remote.rs485, remote.rs485_flags, bytes(master.tx))
        master.tx.clear()
    _run(build_remote_tasks(remote), [])
    if remote.tx:
        _load(master.rs485, master.rs485_flags, bytes(remote.tx))
        remote.tx.clear()
    _run(build_master_tasks(master), [])


def _status_case(body: bytes, order: str, bit6: int, expected: tuple[str, str, str, str]) -> None:
    remote = RemoteApp()
    master = MasterApp()
    remote.now_ms = 1000
    master.now_ms = 1000
    _load(remote.atu_ring, remote.atu_flags, body)
    _run(build_remote_tasks(remote), [])
    assert remote.state.order == order
    assert remote.state.power_sample_ms == 1000
    assert len(remote.link._pending_status) == 15
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
    if expected[2].endswith("W"):
        assert state.antenna_w is not None
    else:
        assert state.antenna_w is None


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
