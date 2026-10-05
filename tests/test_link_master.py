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
