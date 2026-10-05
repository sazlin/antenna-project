# Command bytes shared by the master and the remote on the RS485 link.
# Logs and menus use the mnemonic. The wire uses the single byte.

from enum import Enum


class Command(Enum):
    """One master or remote command, with its wire byte and log name."""

    ACK = (0x01, "ACK")
    HHH = (0x02, "HHH")
    RPT = (0x03, "RPT")
    STA = (0x04, "STA")
    RS = (0x05, "RS")
    RR = (0x06, "RR")
    AT0 = (0x10, "AT0")
    AT1 = (0x11, "AT1")
    AT2 = (0x12, "AT2")
    AT3 = (0x13, "AT3")
    AT4 = (0x14, "AT4")
    TUN = (0x20, "TUN")
    BYP0 = (0x21, "BYP0")
    BYP1 = (0x22, "BYP1")
    AM0 = (0x23, "AM0")
    AM1 = (0x24, "AM1")
    TST0 = (0x25, "TST0")
    TST1 = (0x26, "TST1")
    TUP = (0x27, "TUP")
    TDN = (0x28, "TDN")
    TSC = (0x29, "TSC")
    TSL = (0x2A, "TSL")
    SND = (0x30, "SND")
    RCVD = (0x31, "RCVD")
    ERR = (0x32, "ERR")
    RST = (0x33, "RST")
    RST_RDY = (0x34, "RST RDY")
    F86 = (0x35, "F86")

    def __init__(self, byte: int, mnemonic: str) -> None:
        """Store the wire byte and the mnemonic used in logs."""
        self.byte = byte
        self.mnemonic = mnemonic


def _catalog() -> dict[int, Command]:
    """Map each wire byte back to one command."""
    return {command.byte: command for command in Command}


CODE_TO_COMMAND = _catalog()
