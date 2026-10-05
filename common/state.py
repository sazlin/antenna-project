# Current and previous readings for one Pico.
# The master and the remote each keep a LinkState. Commit copies the old
# row before any antenna, LED, or tuner field changes. Rollback is separate.

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass
class LinkState:
    """One row of antenna, expander, and tuner readings, plus the row before it."""

    antenna: int = 0
    relay_mask: int = 0
    led_bits: int = 0
    button_mask: int = 0
    order: str | None = "LC"
    auto: bool = False
    bypass: bool = False
    test_mode: bool = False
    forward_w: float | None = None
    antenna_w: float | None = None
    swr: float | None = None
    inductance_nh: int | None = None
    capacitance_pf: int | None = None
    efficiency_pct: int | None = None
    power_sample_ms: int | None = None
    link_up: bool = True
    banner: str = ""
    previous: LinkState | None = None


def _snapshot(state: LinkState) -> LinkState:
    """Copy the current row. The copy does not keep an older previous row."""
    values = {item.name: getattr(state, item.name) for item in fields(state)}
    values["previous"] = None
    return LinkState(**values)


def _image(state: LinkState) -> dict[str, int]:
    """Return the hardware fields a caller may write back after a rollback."""
    return {
        "antenna": state.antenna,
        "relay_mask": state.relay_mask,
        "led_bits": state.led_bits,
        "button_mask": state.button_mask,
    }


def rollback(state: LinkState) -> dict[str, int]:
    """Restore the saved row. A second call with nothing older returns that image."""
    previous = state.previous
    if previous is None:
        return _image(state)
    for item in fields(state):
        if item.name == "previous":
            continue
        setattr(state, item.name, getattr(previous, item.name))
    state.previous = None
    return _image(state)


def commit(state: LinkState, **changes: object) -> None:
    """Save the current row, then apply the named changes to it."""
    state.previous = _snapshot(state)
    for name, value in changes.items():
        if name not in {item.name for item in fields(state)} or name == "previous":
            raise TypeError(f"unknown state field {name}")
        setattr(state, name, value)
