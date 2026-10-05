# Error codes for the master, the remote, and the ATU-100.
# An ERR frame on RS485 carries the code, the source unit, and the command.

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
