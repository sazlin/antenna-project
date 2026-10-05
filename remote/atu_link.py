# Serial link from the remote Pico to the ATU-100 on UART1.
# The master does not talk to the tuner. One JSON field goes out per line.
# AM0 turns Auto on and AM1 turns Auto off. BYP1 and TST1 turn those modes on. The Auto pair is reversed from the other pairs, matching the client spec.

from common.commands import Command

_OUTBOUND = {
    Command.AM0: b'{"Auto":true}\n',
    Command.AM1: b'{"Auto":false}\n',
    Command.BYP0: b'{"Bypass":false}\n',
    Command.BYP1: b'{"Bypass":true}\n',
    Command.TUN: b'{"Tune":true}\n',
    Command.STA: b'{"Status":true}\n',
    Command.RST: b'{"Reset":true}\n',
}


def encode_command(command: Command) -> bytes:
    """Return the one-field ukoda line for a tuner command."""
    try:
        return _OUTBOUND[command]
    except KeyError as err:
        raise ValueError(f"no ukoda line for {command.mnemonic}") from err
