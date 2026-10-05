from common.protocol import Status, pack_status, unpack_status


def _reading(order: str) -> Status:
    return Status(
        auto=True,
        bypass=False,
        atu_link=True,
        test_mode=False,
        efficiency_valid=True,
        power_valid=True,
        order=order,
        forward_w=100.0,
        swr=1.15,
        inductance_nh=1250,
        capacitance_pf=150,
        efficiency_pct=99,
        antenna=2,
        error_code=0,
        error_source=0,
    )


def test_status_payload_round_trip():
    packed = pack_status(_reading("LC"))
    assert len(packed) == 13
    assert packed[0] == 0b00110101
    assert int.from_bytes(packed[1:3], "little") == 1000
    assert int.from_bytes(packed[3:5], "little") == 115
    restored = unpack_status(packed)
    assert restored == _reading("LC")
    assert restored.order == "LC"

    swapped = pack_status(_reading("CL"))
    assert len(swapped) == 13
    assert swapped[0] & 0x40
    assert unpack_status(swapped).order == "CL"
    cleared = bytes([swapped[0] & ~0x40]) + swapped[1:]
    assert unpack_status(cleared).order == "LC"
