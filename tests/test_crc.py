from common.protocol import crc16_ccitt


def test_ccitt_false_vector():
    assert crc16_ccitt(b"123456789") == 0x29B1
