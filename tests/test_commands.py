from common.commands import CODE_TO_COMMAND, Command


def test_every_spec_command_has_one_byte():
    expected = {
        "ACK": 0x01,
        "HHH": 0x02,
        "RPT": 0x03,
        "STA": 0x04,
        "RS": 0x05,
        "RR": 0x06,
        "AT0": 0x10,
        "AT1": 0x11,
        "AT2": 0x12,
        "AT3": 0x13,
        "AT4": 0x14,
        "TUN": 0x20,
        "BYP0": 0x21,
        "BYP1": 0x22,
        "AM0": 0x23,
        "AM1": 0x24,
        "TST0": 0x25,
        "TST1": 0x26,
        "TUP": 0x27,
        "TDN": 0x28,
        "TSC": 0x29,
        "TSL": 0x2A,
        "SND": 0x30,
        "RCVD": 0x31,
        "ERR": 0x32,
        "RST": 0x33,
        "RST RDY": 0x34,
        "F86": 0x35,
    }
    by_mnemonic = {command.mnemonic: command.byte for command in Command}
    assert by_mnemonic["RST RDY"] == Command.RST_RDY.byte
    assert by_mnemonic == expected
    assert len(set(by_mnemonic.values())) == 28
    assert Command.AT2.byte == 0x12
    assert Command["AT0"].byte == 0x10
    assert CODE_TO_COMMAND[0x23] is Command.AM0
