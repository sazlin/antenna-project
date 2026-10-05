from common.commands import Command
from common.protocol import Frame, encode_frame


def test_encode_at1_matches_known_frame():
    frame = Frame(source=1, destination=2, sequence=1, command=Command.AT1, payload=b"")
    assert encode_frame(frame).hex() == "7e010201110047517f"
