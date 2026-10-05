from common.commands import Command
from common.protocol import Frame, MasterLink, Status, decode_frames, encode_frame, pack_status


def _ack(frame: Frame) -> bytes:
    return encode_frame(
        Frame(
            source=2,
            destination=1,
            sequence=frame.sequence,
            command=Command.ACK,
            payload=bytes([frame.command.byte]),
        )
    )


def test_master_answers_rs_with_rr():
    link = MasterLink(poll_ms=200, reply_timeout_ms=500, reply_tries=3, miss_limit=5)
    hhh = decode_frames(link.poll(200))[0][0]
    link.feed(encode_frame(Frame(2, 1, hhh.sequence, Command.RS, b"")))
    rr = decode_frames(link.poll(200))[0][0]
    assert rr.command is Command.RR
    reading = Status(
        auto=True,
        bypass=False,
        atu_link=True,
        test_mode=False,
        efficiency_valid=True,
        power_valid=True,
        order="LC",
        forward_w=10.0,
        swr=1.10,
        inductance_nh=0,
        capacitance_pf=0,
        efficiency_pct=90,
        antenna=2,
        error_code=0,
        error_source=0,
    )
    link.feed(encode_frame(Frame(2, 1, rr.sequence, Command.SND, pack_status(reading))))
    assert link.status() == reading
    rcvd = decode_frames(link.poll(200))[0][0]
    assert rcvd.command is Command.RCVD


def test_idle_poll_sends_hhh():
    link = MasterLink(poll_ms=200, reply_timeout_ms=500, reply_tries=3, miss_limit=5)
    assert link.poll(0) is None
    raw = link.poll(200)
    frames, leftover = decode_frames(raw)
    assert leftover == b""
    frame = frames[0]
    assert frame.command is Command.HHH
    assert frame.source == 1
    assert frame.destination == 2
    assert frame.sequence == 1
    assert link.poll(201) is None
    assert "TX HHH" in link.log


def test_five_misses_sets_communication_lost():
    link = MasterLink(poll_ms=200, reply_timeout_ms=500, reply_tries=3, miss_limit=5)
    now = 200
    for _ in range(5):
        assert link.poll(now) is not None
        assert link.poll(now + 500) is not None
        assert link.poll(now + 1000) is not None
        assert link.poll(now + 1500) is None
        now += 1700
    assert link.misses == 5
    assert link.link_lost is True
    assert link.display_banner() == "Communication Lost"
    frames, _leftover = decode_frames(link.poll(now))
    link.feed(_ack(frames[0]))
    assert link.link_lost is False


def test_three_tries_then_one_miss():
    link = MasterLink(poll_ms=200, reply_timeout_ms=500, reply_tries=3, miss_limit=5)
    first = decode_frames(link.poll(200))[0][0]
    assert first.sequence == 1
    assert link.poll(699) is None
    second = decode_frames(link.poll(700))[0][0]
    assert second.sequence == 1
    third = decode_frames(link.poll(1200))[0][0]
    assert third.sequence == 1
    assert link.poll(1700) is None
    assert link.misses == 1
    assert link.link_lost is False
    nxt = decode_frames(link.poll(1900))[0][0]
    assert nxt.sequence == 2
    assert nxt.command is Command.HHH


def test_sequence_skips_zero():
    link = MasterLink(poll_ms=200, reply_timeout_ms=500, reply_tries=3, miss_limit=5)
    seen = []
    now = 200
    for _ in range(255):
        raw = link.poll(now)
        frames, _leftover = decode_frames(raw)
        seen.append(frames[0].sequence)
        link.feed(_ack(frames[0]))
        now += 200
    assert seen[0] == 1
    assert seen[-1] == 255
    assert 0 not in seen
    frames, _leftover = decode_frames(link.poll(now))
    assert frames[0].sequence == 1
    assert 0 not in seen
