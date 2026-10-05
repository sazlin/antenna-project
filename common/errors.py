# Error codes for the master, the remote, and the ATU-100.
# An ERR frame on RS485 carries the code, the source unit, and the command.
# Local faults stay on the board that saw them. System faults travel to the master.

from dataclasses import dataclass
from enum import IntEnum


class ErrorCode(IntEnum):
    """One spec error. The integer is the first byte of an ERR payload."""

    FAILED_TO_EXECUTE = 1
    DATA_NOT_AVAILABLE = 2
    RESOURCE_OFFLINE = 3
    COMMUNICATION_LOST = 4
    DATA_CORRUPTED = 5
    HOT_SWITCH = 6
    RELAY_FAULT = 7

    @property
    def code(self) -> int:
        """Return the wire byte for this error."""
        return int(self)

    @property
    def nature(self) -> str:
        """Return the spec text the operator should read for this code."""
        return _NATURE[self]


_NATURE = {
    ErrorCode.FAILED_TO_EXECUTE: "Failed to Execute Command",
    ErrorCode.DATA_NOT_AVAILABLE: "Data Not Available",
    ErrorCode.RESOURCE_OFFLINE: "Resource offline",
    ErrorCode.COMMUNICATION_LOST: "Communication Lost",
    ErrorCode.DATA_CORRUPTED: "Data Corrupted",
    ErrorCode.HOT_SWITCH: "Hot switch",
    ErrorCode.RELAY_FAULT: "Relay fault",
}


class RelayFault(Exception):
    """The latch read back more than one coil, or not the coil just written."""


_SYSTEM = {
    ErrorCode.COMMUNICATION_LOST,
    ErrorCode.HOT_SWITCH,
    ErrorCode.RELAY_FAULT,
    ErrorCode.RESOURCE_OFFLINE,
}


@dataclass
class Fault:
    """One error with the unit that saw it and whether the master must show it."""

    code: ErrorCode
    nature: str
    source: str
    path: tuple[str, ...] = ()
    local: bool = False
    system: bool = False


def make_error(code: ErrorCode, source: str) -> Fault:
    """Build a fault. System codes are the ones both displays must show."""
    system = code in _SYSTEM
    return Fault(code=code, nature=code.nature, source=source, local=not system, system=system)


def propagate(errors: list[Fault]) -> Fault:
    """Carry the original nature from the ATU through the remote to the master."""
    first = errors[0]
    return Fault(
        code=first.code,
        nature=first.nature,
        source=first.source,
        path=("atu", "remote", "master"),
        local=first.local,
        system=first.system,
    )


def banner(error: Fault) -> str:
    """Return the short line the OLED shows for this fault."""
    if error.code is ErrorCode.COMMUNICATION_LOST:
        return "Communication Lost"
    if error.code is ErrorCode.HOT_SWITCH:
        return "Hot switch"
    if error.code is ErrorCode.RELAY_FAULT:
        return "Relay fault"
    return error.nature
