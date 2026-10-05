from common.commands import Command
from common.errors import ErrorCode, banner, make_error, propagate
from common.hal import note_rx_byte
from common.protocol import Frame, decode_frames, encode_frame
from common.scheduler import run_once
from master.tasks import MasterApp, build_master_tasks
from remote.tasks import RemoteApp, build_remote_tasks


def test_atu_timeout_becomes_master_err():
    remote = RemoteApp()
    remote.atu.send(Command.STA, now_ms=0)
    remote.atu.poll(500)
    remote.atu.poll(1000)
    remote.now_ms = 1500
    run_once(build_remote_tasks(remote), interrupt=lambda: None, watchdog=lambda: None)
    frames, _leftover = decode_frames(bytes(remote.tx))
    assert frames[0].command is Command.ERR
    assert frames[0].payload == bytes([3, 3, 0x04])
    assert "emit_atu_offline" not in open("remote/tasks.py", encoding="utf-8").read()
    master = MasterApp()
    assert master.olat.port_b & (1 << 3) == 0
    for byte in bytes(remote.tx):
        note_rx_byte(master.rs485, master.rs485_flags, byte)
    run_once(build_master_tasks(master), interrupt=lambda: None, watchdog=lambda: None)
    assert master.state.banner == "Resource offline"
    assert master.olat.port_b & (1 << 3)


def test_local_fault_stays_off_the_master_until_the_frame():
    remote = RemoteApp()

    class Stuck:
        def __init__(self) -> None:
            self.value = 0
            self.writes: list[int] = []

        def write(self, value: int) -> None:
            self.writes.append(value)
            self.value = value

        def read(self) -> int:
            if self.writes and self.writes[-1] != 0:
                return 0b0011
            return 0 if self.writes else self.value

    remote.latch = Stuck()
    remote.power.forward_w = 0.2
    for byte in encode_frame(Frame(1, 2, 4, Command.AT1, b"")):
        note_rx_byte(remote.rs485, remote.rs485_flags, byte)
    run_once(build_remote_tasks(remote), interrupt=lambda: None, watchdog=lambda: None)
    assert remote.state.banner == "Relay fault"
    master = MasterApp()
    assert master.olat.port_b & (1 << 3) == 0
    for byte in bytes(remote.tx):
        note_rx_byte(master.rs485, master.rs485_flags, byte)
    run_once(build_master_tasks(master), interrupt=lambda: None, watchdog=lambda: None)
    assert master.olat.port_b & (1 << 3)


def test_error_keeps_source_and_nature():
    fault = make_error(ErrorCode.DATA_CORRUPTED, source="atu")
    assert fault.nature == "Data Corrupted"
    assert fault.source == "atu"
    wrapped = propagate([fault])
    assert wrapped.nature == "Data Corrupted"
    assert wrapped.path == ("atu", "remote", "master")
    local = make_error(ErrorCode.FAILED_TO_EXECUTE, source="remote")
    assert local.local is True
    lost = make_error(ErrorCode.COMMUNICATION_LOST, source="master")
    assert lost.system is True
    assert banner(lost) == "Communication Lost"
    assert banner(make_error(ErrorCode.HOT_SWITCH, source="remote")) == "Hot switch"
    assert banner(make_error(ErrorCode.RELAY_FAULT, source="remote")) == "Relay fault"
    assert ErrorCode.RESOURCE_OFFLINE.code == 3
    natures = {code.nature for code in ErrorCode}
    for text in (
        "Failed to Execute Command",
        "Data Not Available",
        "Resource offline",
        "Communication Lost",
        "Data Corrupted",
    ):
        assert text in natures
