from common.commands import Command
from common.protocol import Frame, MasterLink, decode_frames, encode_frame


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
