# Implementation plan

Remote antenna switch and ATU-100 control for two Raspberry Pi Pico 2 W boards. The builder implements this file in order on branch `cursor/antenna-switch-atu100-a6a6`. Do not switch branches. Do not push. Do not open a pull request. Do not edit `PRD.md`, `spec/`, or `IMPLEMENTATION_LOG.md`.

Each task is one behavior. Write the test, run the fail command, write the smallest code that makes that test pass, run the pass command, then commit. Check the task box in this file in that same commit. Do not start the next task while the current test is red. Do not skip a test, mark it xfail, or weaken an assertion.

The repo has no product modules yet. Root `README.md` is a one-line loadout stub. `justfile` is loadout-only. Leave `justfile` alone.

## Builder rules

Read these before the first code change and follow them while editing the matching files.

- `AGENTS.md`. The binding rules are the files under `.cursor/rules/`.
- `.cursor/rules/ponytail.mdc`. Pick the simplest solution that works. No new runtime dependency. No new product module beyond the layout below. Safety behavior and fields the PRD names are not optional.
- `.cursor/rules/pytest.mdc`. One outcome per test. Names say what the operator would observe. Mock UART, I2C, and pins. No hardware, network, or XC8 in the host suite.
- `.cursor/rules/python-code-style.mdc`. Short functions, type annotations on public functions, dataclasses for structured data, enums for closed sets. The PRD overrides the comment section: see the next paragraph.
- `.cursor/rules/commit-style.mdc`. One cohesive conventional commit per task, `type: imperative summary`. Inspect the staged diff before committing. No Cursor co-author trailer.
- `.cursor/rules/repo-conventions.mdc`. Stay on this branch. Do not commit secrets or generated cache files.
- `.claude/skills/unslop/SKILL.md`. Comments and docs use plain sentences. No chatbot phrasing, no em dash, no decorative emphasis.

Comment override, PRD wins. `python-code-style.mdc` says a one-line docstring on public functions and no docstring on obvious private helpers. This project does the opposite where they conflict. Every module starts with a comment that says what the module is for and where it sits between the master, the remote, the relays, and the ATU-100. Every function, including private helpers, has a docstring. Non-obvious lines say why, for a reader who knows radio and basic Python. Keep each function on one job. Do not split `set_antenna` so the single-relay rule is spread across helpers. The rule has to be readable in that one function.

Host boundary. Tests run under CPython 3.12 with pytest. The only module that may name `machine` is `common/hal.py`, and that import is a top-level `try/except ImportError` because the host has no `machine` module. Document that reason in the `hal.py` module comment. No other file imports `machine` or `uasyncio`. Do not use `uasyncio`. The spec asks for a cooperative loop. There is no ruff, black, or mypy config in this repo. Do not add those tools. The host check is pytest plus `python3 -m compileall`.

Install pytest once, as a host tool, not as a product dependency. Do not add a requirements file.

```bash
python3 -m pip install 'pytest>=7'
```

Run every fail and pass command from `/workspace`.

## Assumptions

Copy client decisions 1 through 8, verbatim, to the top of `docs/ASSUMPTIONS.md` when that task is reached. Then record every engineering assumption below it, with the config name or the doc section that changes it.

Client decisions, already fixed by the PRD.

1. Hot-switch protection. Refuse an antenna change while the ATU-100 reports more than 1 W forward. Threshold and enable live in config. The check runs only when the serial link is reporting power.
2. On RS485 link loss, keep the current antenna. Show `Communication Lost` on both displays. Do not drop a relay because the master went quiet.
3. ATU-100 link is the ukoda serial firmware, not RA6/RA7 bit-bang. MPLAB X and XC8. The client has a PICkit 3 or similar.
4. Test mode is direct L/C relay commands from the remote. No ATU-100 power cycle.
5. Master buttons: Up, Down, Left, Right, Select, Tune, A/M, Bypass, Antenna Select, Menu. Master LEDs: Link OK, Error, Auto Mode, Bypass, RF Present. Map in `master/config.py`.
6. Remote buttons: Up, Down, Left, Right, Select. Remote LEDs: Link OK, Error. Map in `remote/config.py`.
7. Break-before-make delay 100 ms, configurable.
8. Identical Pico pin assignments on both boards. Never GPIO 23, 24, 25, or 29.

Engineering assumptions. These are choices the PRD left open.

- A1. RS485 frame is the byte layout in "Frozen protocol" below. Change it only in `common/protocol.py` and `docs/PROTOCOL.md` together. Baud is `RS485_BAUD` (115200 8N1). The U094 has no DE pin. Do not assign a direction GPIO.
- A2. CRC is CRC-16/CCITT-FALSE, polynomial 0x1021, init 0xFFFF, no reflection, xorout 0. The on-wire CRC is little-endian.
- A3. Master reply timeout is `REPLY_TIMEOUT_MS` (500). A new command is sent at most `REPLY_TRIES` (3) times, counting the first send. Five missed polls (`MISS_LIMIT`) set link loss on the master. Poll period is `POLL_MS` (200) when the master is idle. The remote uses a separate silence timer, `REMOTE_SILENCE_MS` (2000), counted from the last accepted frame. 2000 is greater than 500 so one outstanding reply wait is not silence. Change the remote timer in `remote/config.py`. The master miss counter stays in `common/protocol.py`.
- A4. `set_antenna` is the only function that turns a relay coil on. `force_all_off` only writes zero. F86, boot, reset, and watchdog use `force_all_off` and ignore the hot-switch interlock. AT0 through AT4 go through `apply_antenna_command`, which checks the interlock first. A display or menu exception does not drop relays. `RelayFault` does.
- A5. "Reporting power" means a forward-power sample whose age is under `POWER_STALE_MS` (1000). The sample is the `Forward` field from assumption A12. A stale sample, fallback mode, `forward_w is None`, or a status that has efficiency but no `Forward` does not block an antenna change. Refusal is strict greater-than `HOT_SWITCH_WATTS` (1.0). 1.0 W is allowed. Antenna watts are never compared with the threshold.
- A6. Asking for the antenna that is already selected does not open the coil.
- A7. ukoda `main.c` sends numbers with one decimal place when EEPROM high-power mode is off (`sft = 1`). That meets the 0.1 W display need. A one-line fork is still required, for the reason in A12, not because the decimal place is missing. `atu100_firmware/README.md` records the pinned upstream hex, the unified diff, and the build steps. The host suite does not compile XC8. The wire key for efficiency is `efficency` in the C source. Also accept `Efficency`.
- A8. RST sends `{"Reset":true}` and does not send `{"x":true}`. The `x` name resets the PIC as soon as the closing quote arrives. Document `x` in `docs/ATU_LINK.md` as unused.
- A9. Test-mode steps follow EXT firmware with 7 L and 7 C. `L_mult` is 4, so the mask counts from 0 through 127. `RelayC` bit 7 set means order LC. Default order is LC. Banks and counts are `INDUCTOR_COUNT` and `CAPACITOR_COUNT` in `remote/config.py`.
- A10. Fallback mode and the serial UART must not be wired at the same time. Both want RB1 and RB2. `ATU_MODE` is `serial` or `fallback`. Fallback has no power sample, so the interlock stays inactive. TST, TUP, TDN, TSC, and TSL return `Data Not Available` in fallback.
- A11. Fallback press widths, taken from v3.2 `button_proc`: a Tune press still held after 250 ms is tune, a press released before that is reset. Use `TUNE_LONG_MS` 400 and `TUNE_SHORT_MS` 100. Auto and Bypass are toggles after the 50 ms debounce. Use `BUTTON_TOGGLE_MS` 80. Power-up default is manual and not bypass. The remote remembers the last fallback state and presses only when the requested state differs.
- A12. Choice: a one-line firmware fork, not display-side reconstruction. In ukoda `show_pwr`, when test mode is off, EEPROM cell 0x33 (`e_c_b_Loss_ind`) is on, and internal power is at least 10 (1.0 W), `g_i_Power_report` is replaced with antenna power `p_ant`. `send_state` then sends that value as `Power`. Forward watts are not in the object. Efficiency is capped at 99 after the multiply, so `Power * 100 / efficiency` is the wrong way back to forward watts, and it is the wrong direction for the hot-switch check. The fork adds `Forward` from `g_i_Power` in `send_state`, marked `// REMOTE LINK`. Parser rules: `Forward` is forward watts. `Power` is antenna watts when `efficency` or `Efficency` is present, and forward watts only when that field is absent. Never set antenna watts to forward watts times efficiency. Show the efficiency screen when forward watts are at least 1.0, efficiency was present, and antenna watts were present. Otherwise show L and C. The percent text is capped at 99. The antenna line stays the `Power` value. Where to change the fork text: `atu100_firmware/README.md`. Where to change the screen rule: `common/display.py`.
- A13. Display strings follow the PRD examples, including one decimal on power above 10 W. The stock OLED text `PWR=0.0W` is not what we show.
- A14. Line order follows the stock SW flag. JSON `Order` `LC` puts L on line 3 and C on line 4. `CL` swaps those lines. Bypass marker wins over the Auto marker because the stock code writes `.` only when Auto is on and bypass is off.
- A15. Shared Pico GPIOs are identical and listed below. The MCP23017 bit maps differ because the boards do not have the same buttons. Decision 8 applies to the Pico header, not to every expander bit.
- A16. Master Antenna Select cycles AT1, AT2, AT3, AT4, then back to AT1. It does not select AT0. AT0 is the menu item `All off`.
- A17. Error LED stays on until the next successful ACK, or until link loss clears for `Communication Lost`. RF Present LED is on when the last fresh forward power is greater than `HOT_SWITCH_WATTS`.
- A18. Device boot runs `/main.py`. Flash copies `master/main.py` or `remote/main.py` to `/main.py` and copies the package directory too. Imports inside the repo stay `master.config` and `remote.config`. Do not add a second copy of `main.py` at the repo root.
- A19. MicroPython firmware is v1.29.0 (2026-08-24) for `RPI_PICO2_W`.
- A20. A scheduler exception other than `RelayFault` is a local error. The loop continues and the antenna is left as it is.
- A21. `LinkState` stores the relay coil mask, the LED bit mask, the last button mask, and `order` (`LC` or `CL`). `order` is stored from the JSON `Order` field. It is not derived later. The other tuner readings are the ones listed in task 20. Two I/O groups stay out of the table. The SSD1306 framebuffer is derived by `publish` in `common/display.py` from `LinkState`, so a rollback re-renders instead of storing pixels. Optocoupler coils are pulses owned by `remote/button_emulation.py`, not levels to restore. A restored pulse would press Tune, Auto, or Bypass again. After `RelayFault`, do not write a previous nonzero `relay_mask` back to the latch. `safe_off` leaves the mask at 0. The previous snapshot stays for the log. Boot starts from a fresh `LinkState` and does not write a previous mask.

## Safety invariants

These are tested, not only documented.

- `set_antenna` never leaves more than one relay bit set. On any illegal latch or readback it writes 0 and raises `RelayFault`.
- Boot, RST, watchdog restart, F86, and `RelayFault` end with all relay bits clear.
- Link loss does not call `set_antenna` or `force_all_off`.
- `apply_antenna_command` returns `HOT_SWITCH` and does not call `set_antenna` when fresh forward power is greater than the threshold.
- F86 still clears the coils when power is above the threshold.

## Layout

```
common/protocol.py
common/commands.py
common/state.py
common/scheduler.py
common/mcp23017.py
common/ssd1306.py
common/display.py
common/menu.py
common/buttons.py
common/errors.py
common/hal.py
master/main.py
master/config.py
master/tasks.py
remote/main.py
remote/config.py
remote/tasks.py
remote/relays.py
remote/atu_link.py
remote/button_emulation.py
atu100_firmware/README.md
tests/
docs/README.md
docs/PROTOCOL.md
docs/ATU_LINK.md
docs/WIRING.md
docs/FLASHING.md
docs/ASSUMPTIONS.md
docs/CUSTOMIZING.md
docs/TEST_PLAN.md
SUMMARY.md
```

Deviation from the PRD tree. `common/hal.py` is the `machine` import boundary the host constraints require. `atu100_firmware/` holds `README.md` and the unified diff from assumption A12. It does not vendor the rest of the ukoda tree. `pytest.ini` is host-only. Record these in `docs/ASSUMPTIONS.md`.

Empty `__init__.py` files in `common/`, `master/`, and `remote/` so the packages import. Create them in task 01.

## Frozen protocol

Start byte `0x7E`. End byte `0x7F`. Escape byte `0x7D`. A data byte equal to start, end, or escape is sent as `0x7D` followed by the byte XOR `0x20`. CRC and length are over the unescaped body.

Body, in order: source, destination, sequence, command, length, payload. Then CRC-16/CCITT-FALSE, low byte first, then the end byte.

Source and destination: master `1`, remote `2`. Sequence is an integer 1..255, skipping 0.

Command bytes:

| Mnemonic | Byte |
| --- | --- |
| ACK | 0x01 |
| HHH | 0x02 |
| RPT | 0x03 |
| STA | 0x04 |
| RS | 0x05 |
| RR | 0x06 |
| AT0 | 0x10 |
| AT1 | 0x11 |
| AT2 | 0x12 |
| AT3 | 0x13 |
| AT4 | 0x14 |
| TUN | 0x20 |
| BYP0 | 0x21 |
| BYP1 | 0x22 |
| AM0 | 0x23 |
| AM1 | 0x24 |
| TST0 | 0x25 |
| TST1 | 0x26 |
| TUP | 0x27 |
| TDN | 0x28 |
| TSC | 0x29 |
| TSL | 0x2A |
| SND | 0x30 |
| RCVD | 0x31 |
| ERR | 0x32 |
| RST | 0x33 |
| RST_RDY | 0x34 |
| F86 | 0x35 |

`Command.RST_RDY.mnemonic` is the string `RST RDY`.

Known vector. Body `01 02 01 11 00` is an AT1 from master to remote, sequence 1, empty payload. CRC is `0x5147`. Full frame hex is `7e010201110047517f`. ASCII `123456789` CRC is `0x29B1`.

ACK payload is one byte, the command being acknowledged. ERR payload is three bytes: error code, source, failed command. Sources: master 1, remote 2, atu 3.

SND payload, 13 bytes, little-endian multi-byte fields:

1. flags. bit0 auto, bit1 bypass, bit2 atu link up, bit3 test mode, bit4 efficiency valid, bit5 power valid, bit6 set when Order is CL and clear when Order is LC. Bit 6 was free. The payload stays 13 bytes.
2. forward watts times 10, uint16.
3. SWR times 100, uint16.
4. inductance nH, uint16.
5. capacitance pF, uint16.
6. efficiency percent, uint8.
7. selected antenna 0..4, uint8.
8. error code, uint8, 0 if none.
9. error source, uint8.

Error codes: `FAILED_TO_EXECUTE` 1, `DATA_NOT_AVAILABLE` 2, `RESOURCE_OFFLINE` 3, `COMMUNICATION_LOST` 4, `DATA_CORRUPTED` 5, `HOT_SWITCH` 6, `RELAY_FAULT` 7.

RS/RR on a polled bus. The remote never transmits first. A poll with nothing queued is HHH. If the remote has a new status, it answers that poll with RS and an empty payload, and it does not discard the status. The master then sends RR. The remote answers SND and clears the pending status. The master then sends RCVD. The remote answers ACK. A real command such as AT1 is executed and ACKed even while status is pending. The status handshake continues on the next idle poll. STA skips the handshake and is answered with SND directly. RPT is answered with the previous reply body and the new sequence. A duplicate sequence does not run the action again. It resends the cached reply. A duplicate that arrives before `finish` sends nothing.

Log lines use mnemonics. Example: `TX AT1`, `RX ACK AT1`.

## Frozen pins

Both `master/config.py` and `remote/config.py` define the same Pico pins. Remote-only signals stay reserved on the master so those GPIOs are not reused.

- I2C0 SDA GPIO 8, SCL GPIO 9, 400 kHz. OLED `0x3C`. MCP23017 `0x20`.
- UART0 RS485 TX GPIO 0 to U094 yellow UART_RX. RX GPIO 1 from U094 white UART_TX. Baud 115200.
- UART1 ATU TX GPIO 4, RX GPIO 5, baud 4800. Reserved on the master.
- MCP23017 INTA GPIO 10, INTB GPIO 11.
- Forbidden, and absent from both maps: 23, 24, 25, 29.

Master MCP23017, inputs active low with pull-ups, LED outputs active high:

- GPA0 Up, GPA1 Down, GPA2 Left, GPA3 Right, GPA4 Select, GPA5 Tune, GPA6 A/M, GPA7 Bypass.
- GPB0 Antenna Select, GPB1 Menu.
- GPB2 Link OK, GPB3 Error, GPB4 Auto Mode, GPB5 Bypass, GPB6 RF Present.

Remote MCP23017:

- GPA0 Up, GPA1 Down, GPA2 Left, GPA3 Right, GPA4 Select.
- GPA5 Link OK, GPA6 Error.
- GPB0 relay 1, GPB1 relay 2, GPB2 relay 3, GPB3 relay 4.
- GPB4 Tune opto, GPB5 A/M opto, GPB6 Bypass opto. Used only in fallback mode.

## Frozen ATU JSON

One field per message, LF terminated, no spaces required. Exact outbound bytes:

- AM0 `{"Auto":true}\n`
- AM1 `{"Auto":false}\n`
- BYP0 `{"Bypass":false}\n`
- BYP1 `{"Bypass":true}\n`
- TUN `{"Tune":true}\n`
- STA `{"Status":true}\n`
- RST `{"Reset":true}\n`
- Relay step `{"RelayI":0}\n`, `{"RelayI":1}\n`, `{"RelayC":128}\n` (step 0 plus bit 7), `{"RelayC":129}\n` (step 1 plus bit 7), `{"RelayC":130}\n` (step 2 plus bit 7). Bit 7 is added only on `RelayC`. The L or C field stays in 0..127.

Outbound messages stay one field and one line. Inbound ukoda objects do not. `json_start` sends `{\n`. Each name is indented two spaces, then a quote, the name, a quote, a colon, and a space. Fields are separated by `,\n`. `json_end` sends `\n}\n`. An `Event` object is a separate object of that same shape. The parser appends bytes until the braces balance, then parses that slice. A partial object stays buffered. An `Event` object is ignored. It is not `DATA_CORRUPTED`.

Module comment in `remote/atu_link.py` must contain this sentence: `AM0 turns Auto on and AM1 turns Auto off. BYP1 and TST1 turn those modes on. The Auto pair is reversed from the other pairs, matching the client spec.`

Watts are already watts. Do not divide by 10. `Inductance` is nH. `Capacitance` is pF. `SWR` is the displayed ratio. Field roles are assumption A12. Normal reply timeout `ATU_TIMEOUT_MS` 500. Tune wait `TUNE_TIMEOUT_MS` 30000. Retries `ATU_TRIES` 3.

## Frozen display

Four lines, 16 columns, marker in column 16 of line 1.

- Power `100.0W`, `5.0W`, `0.1W`.
- SWR `1.15`, `1.00`.
- L from nH `1.25uH` for 1250, `0.05uH` for 50.
- C `150pF`, `0pF`.
- Auto and not bypass: last character `.`
- Bypass: last character `_`
- Otherwise a space.
- Efficiency screen for forward 100.0 W, antenna 99.0 W, SWR 1.15, efficiency 99, auto: `100.0W         .`, `1.15`, `99.0W`, `99%`. Line 1 is `Forward`. Line 3 is `Power`. Do not multiply those two.

## Frozen menu

Both menus are data, not hard-coded screens.

Master and remote, same labels:

- Antenna: Antenna 1, Antenna 2, Antenna 3, Antenna 4, All off.
- Tuner: Tune, Auto, Manual, Bypass on, Bypass off, Test on, Test off, Step up, Step down, Select C, Select L, Status, Reset tuner.
- Shutdown (master only).
- Exit Menu.

Right enters a child. Left returns to the parent. Up and Down move. Select on a leaf returns the handler name and exits. Select on Exit Menu returns `exit` and runs no command. Remote handlers still return when `link_up` is false.

Handler names: `at1` `at2` `at3` `at4` `at0` `tun` `am0` `am1` `byp1` `byp0` `tst1` `tst0` `tup` `tdn` `tsc` `tsl` `sta` `rst` `f86` `exit`.

## Tasks

Follow the file from top to bottom. Tasks 63, 64, 65, and 66 keep those numbers so the review notes stay attached to them, and they sit where their helpers already exist.

### Task 01. CRC-16/CCITT-FALSE

- [x] Files: `pytest.ini`, `common/__init__.py`, `master/__init__.py`, `remote/__init__.py`, `common/protocol.py`, `tests/test_crc.py`.

Failing test in `tests/test_crc.py`:

```python
from common.protocol import crc16_ccitt


def test_ccitt_false_vector():
    assert crc16_ccitt(b"123456789") == 0x29B1
```

`pytest.ini`:

```ini
[pytest]
testpaths = tests
pythonpath = .
```

Fail command: `python3 -m pytest tests/test_crc.py::test_ccitt_false_vector -q`

The import fails because `crc16_ccitt` does not exist yet.

Implementation: `crc16_ccitt` as specified in Frozen protocol. Module comment and docstring. No other protocol code in this task.

Pass command: the same pytest command.

Commit: `feat: add CRC-16/CCITT-FALSE for RS485 frames`

### Task 02. Command catalog

- [x] Files: `common/commands.py`, `tests/test_commands.py`.

Failing test: build a dict of mnemonic to byte for every row in the Frozen protocol table, including `RST RDY` mapping to `Command.RST_RDY`. Assert 28 unique bytes, one per Frozen protocol row from ACK through F86, including `RST_RDY` at `0x34` and `F86` at `0x35`. Also assert `Command.AT2.byte == 0x12` (the spec typo AT22 is not a name), `Command["AT0"].byte == 0x10`, and `CODE_TO_COMMAND[0x23] is Command.AM0`.

Fail command: `python3 -m pytest tests/test_commands.py::test_every_spec_command_has_one_byte -q`

Implementation: `class Command(Enum)` with `.byte` and `.mnemonic`. `CODE_TO_COMMAND` dict. Docstrings.

Pass command: the same command.

Commit: `feat: list every master and remote command byte`

### Task 03. Encode the AT1 frame

- [x] Files: `common/protocol.py`, `tests/test_frame.py`.

Failing test:

```python
from common.commands import Command
from common.protocol import Frame, encode_frame


def test_encode_at1_matches_known_frame():
    frame = Frame(source=1, destination=2, sequence=1, command=Command.AT1, payload=b"")
    assert encode_frame(frame).hex() == "7e010201110047517f"
```

Fail command: `python3 -m pytest tests/test_frame.py::test_encode_at1_matches_known_frame -q`

Implementation: `Frame` dataclass and `encode_frame`. Empty payload, no escaping needed for this vector. CRC over the five body bytes.

Pass command: the same command.

Commit: `feat: encode an AT1 RS485 frame`

### Task 04. Decode the AT1 frame

- [x] Files: `common/protocol.py`, `tests/test_frame.py`.

Failing test: `decode_frames(bytes.fromhex("7e010201110047517f"))` returns one frame with `command is Command.AT1`, sequence 1, empty payload, and an empty leftover.

Fail command: `python3 -m pytest tests/test_frame.py::test_decode_at1_known_frame -q`

Implementation: parser that waits for start, reads the unescaped body, checks CRC and end. Do not accept a bad frame in this function. This task only covers the valid frame.

Pass command: the same command.

Commit: `feat: decode an AT1 RS485 frame`

### Task 05. Escape binary payloads

- [x] Files: `common/protocol.py`, `tests/test_frame.py`.

Failing test: payload `bytes([0x7E, 0x00, 0x7D, 0x7F])` round-trips through `encode_frame` and `decode_frames`. The encoded form contains `7d 5e`, `7d 5d`, and `7d 5f` for those three special bytes, and the decoded payload equals the original.

Fail command: `python3 -m pytest tests/test_frame.py::test_payload_special_bytes_round_trip -q`

Implementation: escape on encode, unescape on decode, CRC over the raw payload.

Pass command: the same command.

Commit: `feat: escape start, end, and escape bytes in RS485 payloads`

### Task 06. Reject a truncated frame

- [x] Files: `common/protocol.py`, `tests/test_frame.py`.

Failing test: `decode_frames(bytes.fromhex("7e010201110047"))` returns no frames and keeps those bytes as leftover. It does not raise.

Fail command: `python3 -m pytest tests/test_frame.py::test_truncated_frame_waits -q`

Implementation: return leftover until the end byte is present. Do not treat a short buffer as corruption.

Pass command: the same command.

Commit: `feat: hold a partial RS485 frame until it ends`

### Task 07. Reject a bad CRC

- [x] Files: `common/protocol.py`, `tests/test_frame.py`.

Failing test: flip the CRC low byte of the known AT1 frame to `0x00`. `decode_frames` returns no frames and a leftover that does not include the corrupted frame. The following byte `0x7E` plus a second valid AT1 frame still decodes as one AT1. The corrupted frame is dropped, not delivered.

Fail command: `python3 -m pytest tests/test_frame.py::test_bad_crc_is_dropped -q`

Implementation: on CRC failure, resync at the next start byte after the one that opened the bad frame.

Pass command: the same command.

Commit: `feat: drop an RS485 frame with a bad CRC`

### Task 08. Reject a length that does not match

- [x] Files: `common/protocol.py`, `tests/test_frame.py`.

Failing test: build a buffer whose length byte is 2 but only one payload byte is present before a correct CRC of a different body. `decode_frames` returns no frames. A later valid AT1 still decodes.

Fail command: `python3 -m pytest tests/test_frame.py::test_length_mismatch_is_dropped -q`

Implementation: the CRC check covers the length that was declared. A mismatch fails the CRC or an explicit length check. Either way the frame is not returned.

Pass command: the same command.

Commit: `feat: drop an RS485 frame whose length does not match`

### Task 09. Status payload round trip

- [x] Files: `common/protocol.py`, `tests/test_status_payload.py`.

Failing test: `pack_status` then `unpack_status` for auto on, bypass off, atu link up, not in test, efficiency valid, power valid, order `LC`, forward 100.0, SWR 1.15, 1250 nH, 150 pF, efficiency 99, antenna 2, error 0. Flags byte equals `0b00110101`. Bit 6 is clear. Forward uint16 equals 1000. SWR uint16 equals 115. The packed length is 13. The same reading with order `CL` packs 13 bytes, sets flags bit 6, and `unpack_status` restores order `CL`. Clearing bit 6 restores order `LC`. Task 20 still stores `order` on `LinkState`. Task 30 still parses JSON `Order`. Task 37 still formats LC and CL locally.

Fail command: `python3 -m pytest tests/test_status_payload.py::test_status_payload_round_trip -q`

Implementation: the 13-byte layout in Frozen protocol. Set flags bit 6 only for `CL`. Reject a short buffer by raising `ValueError`. Do not add a 14th byte.

Pass command: `python3 -m pytest tests/test_status_payload.py::test_status_payload_round_trip tests/test_main_loop.py::test_atu_status_is_committed_and_sent -q`

`test_atu_status_is_committed_and_sent` is written in task 64. This task's own gate, before that test exists, is `python3 -m pytest tests/test_status_payload.py::test_status_payload_round_trip -q`. After task 64, the paired command above must pass.

Commit: `feat: pack tuner status into the SND payload`

### Task 10. Master idle poll is HHH

- [x] Files: `common/protocol.py`, `tests/test_link_master.py`.

Failing test: `MasterLink(poll_ms=200, reply_timeout_ms=500, reply_tries=3, miss_limit=5)`. `poll(0)` returns None. `poll(200)` returns one encoded frame whose command is HHH, source 1, destination 2, sequence 1. `poll(201)` returns None while that reply is outstanding. Log contains `TX HHH`.

`test_sequence_skips_zero`: acknowledge each idle poll so the next sequence can advance. The frame whose sequence byte is 255 is valid. The next new poll uses sequence 1. No frame in that run has sequence 0.

Fail command: `python3 -m pytest tests/test_link_master.py::test_idle_poll_sends_hhh -q`

Also run `python3 -m pytest tests/test_link_master.py::test_sequence_skips_zero -q` before the implementation. It fails first for the same reason.

Implementation: `MasterLink` with a fake clock passed in as `now_ms`. No UART object. No sleep. The sequence counter wraps from 255 to 1.

Pass command: `python3 -m pytest tests/test_link_master.py::test_idle_poll_sends_hhh tests/test_link_master.py::test_sequence_skips_zero -q`

After task 27, this paired command must pass too. It names both new tests: `python3 -m pytest tests/test_link_master.py::test_sequence_skips_zero tests/test_relays.py::test_missing_power_does_not_block -q`.

Commit: `feat: poll the remote with HHH when the master is idle`

### Task 11. Retry the same sequence, then count a miss

- [x] Files: `common/protocol.py`, `tests/test_link_master.py`.

Failing test: after `poll(200)` sends sequence 1, `poll(699)` returns None (499 ms later). `poll(700)` returns the same sequence 1 HHH again. `poll(1200)` returns the third copy. `poll(1700)` returns None and `misses == 1`. The next idle poll uses sequence 2. `link_lost` is still false.

Fail command: `python3 -m pytest tests/test_link_master.py::test_three_tries_then_one_miss -q`

Implementation: `reply_tries` counts every transmit of that poll. The third timeout increments `misses` and frees the master to send a new sequence.

Pass command: the same command.

Commit: `feat: retry one poll three times before counting a miss`

### Task 12. Five misses set link loss

- [x] Files: `common/protocol.py`, `tests/test_link_master.py`.

Failing test: drive five missed polls with no inbound bytes. After the fifth miss `link_lost` is true. `display_banner()` returns `Communication Lost`. A later valid ACK for the current sequence clears `link_lost`.

Fail command: `python3 -m pytest tests/test_link_master.py::test_five_misses_sets_communication_lost -q`

Implementation: `miss_limit` 5. Banner text is exactly `Communication Lost`.

Pass command: the same command.

Commit: `feat: show Communication Lost after five missed polls`

### Task 13. Remote ignores a duplicate sequence

- [x] Files: `common/protocol.py`, `tests/test_link_remote.py`.

Failing test: feed an encoded AT1 sequence 7 to `RemoteLink.on_bytes`. The result is `(None, Action(Command.AT1, antenna=1))`. Feed the same frame again before `finish`. The result is `(None, None)`. Call `finish(action)` and capture the ACK bytes. Feed the same frame a third time. The result is those same ACK bytes and action None. Decode the ACK: command ACK, payload byte `0x11`, sequence 7.

Fail command: `python3 -m pytest tests/test_link_remote.py::test_duplicate_at1_does_not_repeat -q`

Implementation: `Action` frozen dataclass with `command` and `antenna: int | None`. `RemoteLink.finish` caches the reply. No relay hardware in this module.

Pass command: the same command.

Commit: `feat: resend the cached reply for a duplicate sequence`

### Task 14. RS, RR, SND, RCVD handshake

- [x] Files: `common/protocol.py`, `tests/test_link_remote.py`, `tests/test_link_master.py`.

Failing test, remote side: `notify_status(payload)` then an HHH poll returns a frame whose command is RS and whose payload is empty. A following AT2 returns action antenna 2 and, after `finish`, ACK of AT2. The status is still pending. The next HHH returns RS again. An RR returns SND whose payload equals the pending bytes, and the pending flag clears. A second RR with nothing pending returns ACK of RR. An RCVD returns ACK of RCVD.

Failing test, master side: script the peer by feeding the master the RS frame, then assert the next `poll` command is RR. Feed SND, assert `status()` unpacks and the next command is RCVD.

Fail command: `python3 -m pytest tests/test_link_remote.py::test_status_handshake_survives_at2 -q`

Do both tests in this task. The fail command is the remote test. Run the master test as well before the commit. Both must fail first for a missing handshake, then pass.

Implementation: pending status flag on the remote. Master `expect` state moves `idle -> saw_rs -> saw_snd -> idle`.

Pass command: `python3 -m pytest tests/test_link_remote.py::test_status_handshake_survives_at2 tests/test_link_master.py::test_master_answers_rs_with_rr -q`

Commit: `feat: map RS and RR onto the polled status transfer`

### Task 15. RPT resends the previous reply

- [x] Files: `common/protocol.py`, `tests/test_link_remote.py`.

Failing test: finish an AT3 so a cached ACK exists. A new sequence whose command is RPT returns a frame with the new sequence, command ACK, payload byte `0x13`, and action None. That cache stays in place. This test does not clear it.

`test_rpt_without_cache_is_data_not_available`: a new `RemoteLink` with an empty cache receives RPT. The reply is ERR. Payload byte 0 is `ErrorCode.DATA_NOT_AVAILABLE` (2). Payload byte 1 is source remote (2). Payload byte 2 is `0x03`.

`test_sta_without_status_is_data_not_available`: STA with no queued status payload returns ERR. Payload byte 0 is 2, payload byte 1 is 2, payload byte 2 is `0x04`. A STA that does have a queued payload is still SND, which task 16 asserts. Do not change that test.

Fail command: `python3 -m pytest tests/test_link_remote.py::test_rpt_without_cache_is_data_not_available tests/test_link_remote.py::test_sta_without_status_is_data_not_available -q`

The existing `test_rpt_resends_previous_ack` fails first too, before `RemoteLink` exists. Run it as well.

Implementation: RPT with a cache copies the previous command and payload onto the new sequence and does not clear the cache. RPT with an empty cache, and STA with no status payload, call `fail` with `DATA_NOT_AVAILABLE` and source 2. They do not invent an empty SND.

Pass command: `python3 -m pytest tests/test_link_remote.py::test_rpt_resends_previous_ack tests/test_link_remote.py::test_rpt_without_cache_is_data_not_available tests/test_link_remote.py::test_sta_without_status_is_data_not_available -q`

Commit: `feat: answer RPT with the previous reply`

### Task 16. STA is a direct status reply

- [x] Files: `common/protocol.py`, `tests/test_link_remote.py`.

Failing test: with a status payload queued, a STA frame returns SND with that payload and action None. It does not return RS.

Fail command: `python3 -m pytest tests/test_link_remote.py::test_sta_replies_with_snd -q`

Implementation: STA is the spec request for operational status. Skip RS.

Pass command: the same command.

Commit: `feat: answer STA with SND`

### Task 17. RST then RST RDY

- [x] Files: `common/protocol.py`, `tests/test_link_remote.py`.

Failing test: the first frame after construction, an HHH, returns command `RST_RDY` and mnemonic `RST RDY`. After that, an HHH returns ACK. A RST frame returns action `Command.RST` and, after `finish`, ACK of RST. The next HHH returns `RST RDY` once, then ACK again.

Fail command: `python3 -m pytest tests/test_link_remote.py::test_boot_and_rst_send_ready -q`

Implementation: `ready_notice` flag, set at init and set again by RST. The next reply that is not itself a command ACK is RST RDY. RST's own finish ACK is the command ACK, and the ready notice waits for the following poll.

Pass command: the same command.

Commit: `feat: send RST RDY at boot and after RST`

### Task 18. F86 shuts the command path

- [x] Files: `common/protocol.py`, `tests/test_link_remote.py`.

Failing test: F86 returns action `Command.F86`. After `finish`, ACK payload is `0x35`. A later AT1 returns action None and an ERR frame whose first payload byte is `FAILED_TO_EXECUTE`. `shutdown` stays true until RST, which clears it and returns action RST.

Fail command: `python3 -m pytest tests/test_link_remote.py::test_f86_rejects_later_antenna_commands -q`

Implementation: a flag on `RemoteLink`. The relay module performs the coil work. This task only decides the action.

Pass command: the same command.

Commit: `feat: keep relays commanded off after F86 until RST`

### Task 19. ERR frame carries code, source, and command

- [x] Files: `common/protocol.py`, `common/errors.py`, `tests/test_err_frame.py`.

Failing test: `RemoteLink.fail(Command.AT1, ErrorCode.HOT_SWITCH, source=2)` returns an ERR frame, sequence unchanged, payload `bytes([6, 2, 0x11])`. `ErrorCode.COMMUNICATION_LOST.nature` equals `Communication Lost`. Every spec nature exists: `Failed to Execute Command`, `Data Not Available`, `Resource offline`, `Communication Lost`, `Data Corrupted`.

Fail command: `python3 -m pytest tests/test_err_frame.py::test_hot_switch_err_payload -q`

Implementation: `ErrorCode` enum in `common/errors.py` with `.code` and `.nature`. `class RelayFault(Exception)` lives in that same module and nowhere else. `fail` caches that ERR as the reply for the open sequence. Tasks 22 and 44 import `RelayFault` from `common.errors`. This task defines it early so those imports have one class to share. The coil rule stays inside `set_antenna`.

Pass command: the same command.

Commit: `feat: put the error code and source in the ERR payload`

### Task 20. Commit saves the previous state

- [x] Files: `common/state.py`, `tests/test_state.py`.

Failing test: `LinkState` starts with `antenna == 0`, `relay_mask == 0`, `led_bits == 0`, `button_mask == 0`, `order == "LC"`, and `previous is None`. `commit(state, antenna=2, relay_mask=0b0010, led_bits=0b0001, button_mask=0b0100)` makes those current fields match the new values and the previous fields stay 0. A second commit to antenna 4 and `relay_mask=0b1000` leaves previous antenna 2 and previous `relay_mask` `0b0010`. The previous object is a copy. Mutating the current `relay_mask` after commit does not change `previous.relay_mask`.

`test_commit_stores_lc_order`: `commit(state, order="CL")` sets `state.order` to `CL` and leaves `state.previous.order` as `LC`.

Fail command: `python3 -m pytest tests/test_state.py::test_commit_keeps_an_independent_previous -q`

Also run `python3 -m pytest tests/test_state.py::test_commit_stores_lc_order -q` before the implementation. It fails first.

Implementation: dataclass `LinkState` with antenna, relay_mask, led_bits, button_mask, order (`str | None`, default `"LC"`), auto, bypass, test_mode, forward_w, antenna_w, swr, inductance_nh, capacitance_pf, efficiency_pct, power_sample_ms, link_up, banner. `commit(state, **changes)` copies the old current first, then applies changes. One function. `order` is stored, as assumption A21 says. Groups left out of the table are still the framebuffer and the optocoupler pulses.

Pass command: `python3 -m pytest tests/test_state.py::test_commit_keeps_an_independent_previous tests/test_state.py::test_commit_stores_lc_order -q`

Commit: `feat: save the previous state before a commit`

### Task 21. Rollback restores the previous hardware image

- [x] Files: `common/state.py`, `tests/test_state.py`.

Failing test: commit antenna 1, `relay_mask=0b0001`, `led_bits=0b0010`, `button_mask=0b1000`, then commit antenna 3 and `relay_mask=0b0100`. `rollback(state)` sets antenna back to 1 and returns a dict with `antenna` 1, `relay_mask` `0b0001`, `led_bits` `0b0010`, and `button_mask` `0b1000`. A second rollback with no older snapshot leaves antenna 1 and returns that same image. It does not raise. A normal caller may reapply that dict, including a nonzero `relay_mask`. `RelayFault` does not. Task 46 leaves the latch at 0 and does not write this dict's `relay_mask` after a coil fault.

Fail command: `python3 -m pytest tests/test_state.py::test_rollback_returns_the_previous_antenna -q`

Implementation: `rollback` swaps current back to the stored previous, including the three masks. Do not touch the latch here.

Pass command: `python3 -m pytest tests/test_state.py -q`

Commit: `feat: roll back state and report the image to reapply`

### Task 22. One relay on, or all off

- [x] Files: `remote/relays.py`, `tests/test_relays.py`.

Failing test: a `FakeLatch` records writes and returns the last write from `read`. `set_antenna(latch, 0, delay_ms=100, sleep=sleeper)` writes `[0]` and the sleeper records 100. Start from latch value 0. `set_antenna(latch, 2, delay_ms=100, sleep=sleeper)` writes `[0, 0b0010]` and sleeps 100 between them. The final `read()` is `0b0010`. No write contains more than one bit.

Fail command: `python3 -m pytest tests/test_relays.py::test_set_antenna_one_coil_after_all_off -q`

Implementation: import `RelayFault` from `common.errors`. Do not define that class in this file. The single-relay body stays in `set_antenna`, which is the only function in this module that writes a non-zero latch in this task. The body, in order: read the latch, if more than one bit is set write 0 and raise `RelayFault`, write 0, read back and require 0, if target is 0 return, sleep `delay_ms`, write exactly `1 << (target - 1)`, read back and require that bit. Target is 0..4. Any other target raises `ValueError` before a write. Docstring states that this is the only place a coil is turned on. This import is the P-008 edit. The coil checks are unchanged.

Pass command: the same command.

Commit: `feat: energize at most one antenna relay`

### Task 23. A latch that already has two bits forces all off

- [x] Files: `remote/relays.py`, `tests/test_relays.py`.

Failing test: latch reads `0b0101` before the call. `set_antenna(..., 3, ...)` raises `RelayFault`. The last write is 0. The sleeper was not called.

Fail command: `python3 -m pytest tests/test_relays.py::test_two_bits_already_set_forces_off -q`

Implementation: the check already specified in task 22. This test is the new behavior to satisfy. Do not catch `RelayFault` inside `set_antenna`.

Pass command: the same command.

Commit: `feat: force relays off when two coils read back on`

### Task 24. Readback mismatch forces all off

- [x] Files: `remote/relays.py`, `tests/test_relays.py`.

Failing test: latch `write` of the target bit is followed by `read` returning `0b0011`. `set_antenna(..., 1, ...)` raises `RelayFault` and the last write is 0.

Fail command: `python3 -m pytest tests/test_relays.py::test_readback_mismatch_forces_off -q`

Implementation: the readback check in `set_antenna`. After forcing off, do not try a second target.

Pass command: the same command.

Commit: `feat: force relays off when the latch readback mismatches`

### Task 25. The same antenna does not drop the coil

- [x] Files: `remote/relays.py`, `tests/test_relays.py`.

Failing test: `apply_antenna_command(latch, state, target=2, now_ms=0, forward_w=0.0, sample_ms=0, threshold_w=1.0, enabled=True, stale_ms=1000, delay_ms=100, sleep=sleeper)` with `state.antenna == 2` and latch already `0b0010` returns None and writes nothing. `sleeper` was not called.

Fail command: `python3 -m pytest tests/test_relays.py::test_same_antenna_does_not_cycle -q`

Implementation: `apply_antenna_command` returns None when `state.antenna == target` and the latch already shows that single bit. It does not call `set_antenna`.

Pass command: the same command.

Commit: `feat: leave the selected antenna relay closed`

### Task 26. Hot-switch refusal

- [x] Files: `remote/relays.py`, `tests/test_relays.py`.

Failing test: state antenna 1, latch `0b0001`, `forward_w=1.1`, `sample_ms=0`, `now_ms=500`, threshold 1.0, enabled True, stale 1000. `apply_antenna_command` for target 2 returns `ErrorCode.HOT_SWITCH` and writes nothing. The same call for target 0 also returns `ErrorCode.HOT_SWITCH` and writes nothing.

Fail command: `python3 -m pytest tests/test_relays.py::test_power_above_one_watt_blocks_antenna_change -q`

Implementation: the comparison is `forward_w > threshold_w`. AT0 is a change and is refused too.

Pass command: the same command.

Commit: `feat: refuse an antenna change above the forward power threshold`

### Task 27. Hot-switch allows the boundary and a stale sample

- [x] Files: `remote/relays.py`, `tests/test_relays.py`.

Failing test, three cases in one test function is too many. Write three tests in this task:

- `test_one_watt_is_allowed`: forward 1.0, fresh sample, target 2, latch ends at `0b0010`, return None.
- `test_disabled_interlock_allows_high_power`: enabled False, forward 50.0, target 3, latch ends at `0b0100`.
- `test_stale_power_does_not_block`: sample_ms 0, now_ms 1000, stale_ms 1000, forward 25.0, target 4 is allowed. Age equal to the stale window is stale.
- `test_missing_power_does_not_block`: `forward_w` is None, `enabled` is True, `sample_ms` equals `now_ms` so the timestamp is fresh, target 2. The latch changes to `0b0010`.

Fail command: `python3 -m pytest tests/test_relays.py::test_one_watt_is_allowed -q`

Run the other three as well. All four fail first, then pass.

Implementation: allow when `not enabled` or `now_ms - sample_ms >= stale_ms` or `forward_w is None` or `forward_w <= threshold_w`.

Pass command: `python3 -m pytest tests/test_link_master.py::test_sequence_skips_zero tests/test_relays.py::test_missing_power_does_not_block tests/test_relays.py::test_one_watt_is_allowed tests/test_relays.py::test_disabled_interlock_allows_high_power tests/test_relays.py::test_stale_power_does_not_block -q`

Commit: `feat: allow an antenna change at 1 W or without fresh power`

### Task 28. force_all_off ignores power

- [x] Files: `remote/relays.py`, `tests/test_relays.py`.

Failing test: latch holds `0b1000`. `force_all_off(latch)` writes 0 and does not take a power argument. A second test `test_f86_path_uses_force_all_off` calls the helper `shutdown_relays(latch)` which calls `force_all_off` and returns the reason string `F86`. Reasons `boot`, `reset`, and `watchdog` are the same helper `safe_off(latch, reason)` returning that reason and leaving the latch at 0. `safe_off` does not call `set_antenna`.

Fail command: `python3 -m pytest tests/test_relays.py::test_safe_off_clears_coils_for_boot -q`

Also add `test_safe_off_clears_coils_for_reset`, `test_safe_off_clears_coils_for_watchdog`, and `test_safe_off_clears_coils_for_f86`. Same implementation, four tests, because each entry point is a behavior the PRD lists.

`test_force_all_off_readback_stays_nonzero`: `write(0)` is followed by `read()` returning `0b0001`. `force_all_off` raises `RelayFault`. The last write is 0.

Implementation: import `RelayFault` from `common.errors`. Do not define it here. `force_all_off` writes 0 and reads back. If the readback is not 0, write 0 again and raise `RelayFault`. `safe_off(latch, reason)` calls only `force_all_off` and returns the reason. Allowed reasons: `boot`, `reset`, `watchdog`, `F86`, `fault`. The import is the P-008 edit. `safe_off` still only clears coils.

Pass command: `python3 -m pytest tests/test_relays.py -q`

Commit: `feat: open every relay on boot, reset, watchdog, and F86`

### Task 29. Outbound ukoda JSON, one field

- [ ] Files: `remote/atu_link.py`, `tests/test_atu_json.py`.

Failing test: `encode_command(Command.AM0) == b'{"Auto":true}\n'`, AM1 false, BYP0 false, BYP1 true, TUN, STA, RST match Frozen ATU JSON. `encode_command(Command.AM0)` does not contain `Bypass`. The module source contains the required AM0 sentence from Frozen ATU JSON.

Fail command: `python3 -m pytest tests/test_atu_json.py::test_am0_is_auto_true_alone -q`

Add one test per command listed above. They can live in this task. Each test is its own function.

Implementation: a dict from command to exact bytes. TST and relay commands are not in this dict.

Pass command: `python3 -m pytest tests/test_atu_json.py -q -k encode`

Commit: `feat: map tuner commands onto one ukoda JSON field`

### Task 30. Parse a ukoda status object

- [ ] Files: `remote/atu_link.py`, `tests/test_atu_json.py`.

Failing test `test_parse_multiline_send_state`: `feed` this buffer, which is the `send_state` shape from `json.c` plus the `Forward` field from assumption A12.

```text
{
  "Auto": true,
  "Bypass": false,
  "efficency": 99,
  "Power": 99.0,
  "Forward": 100.0,
  "SWR": 1.15,
  "Order": "LC",
  "Capacitance": 150,
  "Inductance": 1250
}
```

The bytes use `\n` after the opening brace, `,\n` between fields, two leading spaces on each name, one space after each colon, and `\n` before the closing brace. The parsed result has `forward_w` 100.0, `antenna_w` 99.0, `efficiency_pct` 99, `swr` 1.15, `inductance_nh` 1250, `capacitance_pf` 150, `auto` True, `bypass` False, `order` `LC`. `antenna_w` is not `100.0 * 0.99`.

`test_event_object_is_ignored`: feed `{\n  "Event": "Tune"\n}\n`. The result is no status and the error is None. It is not `DATA_CORRUPTED`.

`test_partial_object_stays_buffered`: feed `{\n  "Forward": 1.0`. No status and no error. The fragment remains buffered. Feeding the rest, `,\n  "Power": 1.0\n}\n`, then parses `forward_w` 1.0. There is no efficiency field, so `Power` is also forward watts and `antenna_w` is None.

`test_parse_status_with_source_spelling`: one extra one-line object, `{"Power":8.5,"SWR":1.23,"Inductance":110}\n`, with no efficiency and no `Forward`. `forward_w` is 8.5 and `antenna_w` is None. A one-line object that spells the key `Efficency` and also has `Forward` sets `efficiency_pct` and uses `Power` as `antenna_w`.

Fail command: `python3 -m pytest tests/test_atu_json.py::test_parse_multiline_send_state -q`

Implementation: `feed` appends to a buffer and emits one object each time the braces balance. `json.loads` that slice. Apply assumption A12. Do not split inbound objects on newlines. Outbound commands stay the one-field bytes from task 29. The firmware diff itself is task 58. This task only parses the resulting bytes.

Pass command: `python3 -m pytest tests/test_atu_json.py::test_parse_multiline_send_state tests/test_atu_json.py::test_event_object_is_ignored tests/test_atu_json.py::test_partial_object_stays_buffered tests/test_atu_json.py::test_parse_status_with_source_spelling -q`

Commit: `feat: parse multiline ukoda status and the Forward field`

### Task 31. Malformed JSON does not raise

- [ ] Files: `remote/atu_link.py`, `tests/test_atu_json.py`.

Failing test: `AtuLink` with a fake port. `feed(b'{"Forward":}\n')` returns `ErrorCode.DATA_CORRUPTED` and does not raise. The braces balance, so this is not the partial-object case from task 30. The next fed object `b'{"Forward":1.0}\n'` still parses as forward 1.0 W.

Fail command: `python3 -m pytest tests/test_atu_json.py::test_broken_json_is_data_corrupted -q`

Implementation: catch `json.JSONDecodeError` only after the braces balance. Drop that slice. Keep the half-duplex flag clear so a later command can be sent. Do not treat an unbalanced buffer as corruption.

Pass command: the same command.

Commit: `feat: treat malformed ukoda JSON as data corrupted`

### Task 32. Half duplex and tune busy

- [ ] Files: `remote/atu_link.py`, `tests/test_atu_json.py`.

Failing test `test_second_send_while_waiting_fails`: `send(Command.STA, now_ms=0)` writes `{"Status":true}\n` and `busy` is true. A second `send(Command.AM0, now_ms=10)` writes nothing and returns `ErrorCode.FAILED_TO_EXECUTE`.

`test_status_is_retried_three_times`: the write list is `b'{"Status":true}\n'` at `now_ms` 0, again at 500, and again at 1000. Those are three writes, spaced by `ATU_TIMEOUT_MS`. At `now_ms` 1500, `poll` does not write a fourth copy, `busy` is false, and the result is `ErrorCode.RESOURCE_OFFLINE`. Task 43 puts that code on the RS485 ERR frame.

`test_reply_on_first_try_sends_once`: a status reply arrives before the first timeout. The write list length stays 1. Do not resend after that reply.

`test_tune_uses_the_long_timeout`: `send(Command.TUN, now_ms=0)` stays busy at `now_ms=29999` and clears at `now_ms=30000` if no reply arrived. This test does not require a retry write.

Fail command: `python3 -m pytest tests/test_atu_json.py::test_status_is_retried_three_times -q`

Also run `test_second_send_while_waiting_fails`, `test_reply_on_first_try_sends_once`, and `test_tune_uses_the_long_timeout`. They fail first.

Implementation: one outstanding message. Tune uses `TUNE_TIMEOUT_MS`. Other commands use `ATU_TIMEOUT_MS`. `ATU_TRIES` is 3 writes, counting the first. No `time.sleep`. The scheduler calls `poll`. A reply clears `busy` without another write.

Pass command: `python3 -m pytest tests/test_atu_json.py::test_second_send_while_waiting_fails tests/test_atu_json.py::test_status_is_retried_three_times tests/test_atu_json.py::test_reply_on_first_try_sends_once tests/test_atu_json.py::test_tune_uses_the_long_timeout -q`

Commit: `feat: wait for the ukoda reply before sending again`

### Task 33. Test mode relay masks

- [ ] Files: `remote/atu_link.py`, `tests/test_test_mode.py`.

Each test expects one mask. `TST1` on a new `TestMode()` returns no JSON and sets `active` true. The step starts at 0. TSC and TSL keep that step. They do not zero it.

- `test_tup_from_zero_sends_relay_i_1`: one `TUP` returns `b'{"RelayI":1}\n'`.
- `test_second_tup_sends_relay_i_2`: the second `TUP` returns `b'{"RelayI":2}\n'`.
- `test_tdn_at_zero_sends_relay_i_0`: `TDN` at step 0 returns `b'{"RelayI":0}\n'` and the step stays 0.
- `test_inductor_ceiling_stays_127`: with `inductor_count` 7, a `TUP` at step 127 returns `b'{"RelayI":127}\n'`.
- `test_tst0_sends_reset`: `TST0` returns `b'{"Reset":true}\n'` and `active` is false.
- `test_tsc_from_step_1_sends_relay_c_130`: one `TUP` leaves the step at 1. `TSC` keeps the step at 1. The next `TUP` returns `b'{"RelayC":130}\n'`. 130 is step 2 with bit 7. The L or C field of every mask in these tests is in 0..127. Bit 7 is present only on `RelayC`.
- `test_tst1_enters_test_mode_without_json`: a new `TestMode`, command `TST1`, returns no JSON, `active` is true, and the step is 0. This test does not replace the `RelayI` and `RelayC` cases above.

Fail command: `python3 -m pytest tests/test_test_mode.py::test_tst1_enters_test_mode_without_json -q`

The mask tests fail first as well. Run them before the implementation.

Implementation: `TestMode` in `atu_link.py`. `TST1` only sets `active`. It does not build JSON and it does not use the `encode_command` dict from task 29. Default order LC so bit 7 is set on every `RelayC` value. `RelayI` has no order bit. `L_mult` for 7 elements is 4, so the ceiling is 127. TSC still keeps the step.

Pass command: `python3 -m pytest tests/test_test_mode.py -q`

Commit: `feat: step L and C with ukoda relay masks`

### Task 34. Fallback button presses

- [ ] Files: `remote/button_emulation.py`, `tests/test_fallback.py`.

Failing test: `Fallback(initial_auto=False, initial_bypass=False)`. `press_for(Command.TUN)` returns `[("tune", 400)]`. `press_for(Command.RST)` returns `[("tune", 100)]`. `press_for(Command.AM0)` returns `[("auto", 80)]` and the remembered auto state becomes true. A second AM0 returns `[]`. `press_for(Command.AM1)` returns `[("auto", 80)]`. `press_for(Command.BYP1)` returns `[("bypass", 80)]`. `press_for(Command.TUP)` returns error `DATA_NOT_AVAILABLE` and no press. Same for TDN, TSC, TSL, TST0, TST1. `press_for(Command.STA)` returns that same error.

Fail command: `python3 -m pytest tests/test_fallback.py::test_tune_holds_400_ms -q`

Add the other assertions as separate test functions in this task.

Implementation: the durations from assumption A11. No JSON. No relay masks.

Pass command: `python3 -m pytest tests/test_fallback.py -q`

Commit: `feat: emulate Tune, Auto, and Bypass with stock press times`

### Task 35. Power and SWR text

- [ ] Files: `common/display.py`, `tests/test_display_format.py`.

Failing test: `format_power(100) == "100.0W"`, `format_power(5) == "5.0W"`, `format_power(0.1) == "0.1W"`. `format_swr(1.15) == "1.15"`, `format_swr(1) == "1.00"`.

Fail command: `python3 -m pytest tests/test_display_format.py::test_power_one_decimal -q`

Also `test_swr_two_decimals`.

Implementation: format with the PRD precision. Do not prefix `PWR=` or `SWR=`.

Pass command: `python3 -m pytest tests/test_display_format.py::test_power_one_decimal tests/test_display_format.py::test_swr_two_decimals -q`

Commit: `feat: format forward power and SWR like the spec examples`

### Task 36. Inductance and capacitance text

- [ ] Files: `common/display.py`, `tests/test_display_format.py`.

Failing test: `format_inductance_nh(1250) == "1.25uH"`, `format_inductance_nh(50) == "0.05uH"`, `format_capacitance_pf(150) == "150pF"`, `format_capacitance_pf(0) == "0pF"`.

Fail command: `python3 -m pytest tests/test_display_format.py::test_nanohenries_become_microhenries -q`

Also `test_picofarads`.

Implementation: divide nH by 1000 and show two decimals. C is an integer with a `pF` suffix.

Pass command: `python3 -m pytest tests/test_display_format.py::test_nanohenries_become_microhenries tests/test_display_format.py::test_picofarads -q`

Commit: `feat: format L and C for the tuner screen`

### Task 37. Mode marker and L/C order

- [ ] Files: `common/display.py`, `tests/test_display_format.py`.

Failing test: `screen_lines` for forward 100.0, swr 1.15, 1250 nH, 150 pF, auto True, bypass False, order `LC`, efficiency None returns line 1 `100.0W         .` (16 characters, last is `.`), line 2 `1.15`, line 3 `1.25uH`, line 4 `150pF`. The same reading with bypass True ends line 1 with `_` even if auto is also True. Order `CL` swaps lines 3 and 4.

Fail command: `python3 -m pytest tests/test_display_format.py::test_auto_marker_and_lc_order -q`

Also `test_bypass_marker_wins` and `test_cl_swaps_l_and_c`.

Implementation: `screen_lines(reading) -> tuple[str, str, str, str]`. Pad line 1 to 16 with the marker in the last column.

Pass command: `python3 -m pytest tests/test_display_format.py::test_auto_marker_and_lc_order tests/test_display_format.py::test_bypass_marker_wins tests/test_display_format.py::test_cl_swaps_l_and_c -q`

Commit: `feat: place the Auto and Bypass markers on line 1`

### Task 38. Efficiency screen at 1 W and above

- [ ] Files: `common/display.py`, `tests/test_display_format.py`.

Failing test: `forward_w` 100.0, `antenna_w` 99.0, efficiency 99, swr 1.15, auto True, bypass False returns `("100.0W         .", "1.15", "99.0W", "99%")`. `forward_w` 1.0, `antenna_w` 0.5, efficiency 99, and the same SWR returns the efficiency screen with line 3 `0.5W`, not a product of 1.0 and 0.99. `forward_w` 0.9 with efficiency 99 and `antenna_w` 0.5 returns the L/C screen. Efficiency None at `forward_w` 100.0 returns the L/C screen. Efficiency 100 with `antenna_w` 100.0 displays `99%` and line 3 `100.0W`.

Fail command: `python3 -m pytest tests/test_display_format.py::test_efficiency_screen_at_one_watt -q`

Also `test_efficiency_hidden_below_one_watt` and `test_efficiency_capped_at_99`.

Implementation: show the efficiency screen when `forward_w >= 1.0`, efficiency is not None, and `antenna_w` is not None. Line 1 is `forward_w`. Line 3 is `antenna_w`. Do not multiply. The percent text above 99 is drawn as 99. This matches v3.2 turning the loss screen on at internal power 10, which is 1.0 W. It does not wait for a tune-finished flag. The field roles are assumption A12.

Pass command: `python3 -m pytest tests/test_display_format.py::test_efficiency_screen_at_one_watt tests/test_display_format.py::test_efficiency_hidden_below_one_watt tests/test_display_format.py::test_efficiency_capped_at_99 -q`

Commit: `feat: show antenna power and efficiency from 1 W up`

### Task 39. Display line, character, scrollback, highlight

- [ ] Files: `common/display.py`, `tests/test_display_buffer.py`.

Failing test: `DisplayBuffer()`. `write_line(1, "100.0W")` then `line(1)` equals that string. `write_line(0, "x")` and `write_line(5, "x")` raise `ValueError`. `write_char(2, 1, "A")` puts `A` at column 1 of line 2. `push_scroll("older")` then seven more lines, then one more, leaves 8 stored lines and drops the oldest. `highlight()` is None until `set_highlight(3)`, then it returns 3. `set_highlight(0)` raises `ValueError`.

Fail command: `python3 -m pytest tests/test_display_buffer.py::test_write_line_and_char -q`

Add separate tests for the bad line number, the 8-line scrollback, and highlight.

Implementation: lines 1..4, columns 1..16, scrollback length 8. Store strings. Do not talk to I2C in this module.

Pass command: `python3 -m pytest tests/test_display_buffer.py -q`

Commit: `feat: buffer four OLED lines and a menu highlight`

### Task 40. Menu navigation

- [ ] Files: `common/menu.py`, `tests/test_menu.py`.

Failing test: `Menu(MASTER_MENU)` starts on `Antenna` and is not active until `open_menu()`. After open, `down()` moves to `Tuner`, `up()` from the top wraps to `Exit Menu`, `right()` on Antenna shows `Antenna 1`, `left()` returns to Antenna, `select()` on Antenna 1 returns `at1` and `active` is false. `select()` on Exit Menu returns `exit`. `select()` on a parent does not return a handler. It enters the child, the same as right. Shutdown's select returns `f86`.

Fail command: `python3 -m pytest tests/test_menu.py::test_select_leaf_exits_with_handler -q`

Add tests for wrap, left, Exit Menu, and entering a parent.

Implementation: the menu data in Frozen menu, as a tuple of nodes. Each node is a small dataclass `MenuItem(label, handler, children)`. No OLED calls.

Pass command: `python3 -m pytest tests/test_menu.py -q`

Commit: `feat: navigate the five-button menu`

### Task 41. Remote menu works while the link is down

- [ ] Files: `common/menu.py`, `tests/test_menu.py`.

Failing test: `Menu(REMOTE_MENU, link_up=False)`. Open, enter Antenna, select Antenna 4. The return is still `at4`. `link_up` is not consulted by `select`.

Fail command: `python3 -m pytest tests/test_menu.py::test_remote_select_works_when_link_is_down -q`

Implementation: `REMOTE_MENU` has no Shutdown item. `select` does not look at `link_up`. The flag is stored so task 47 can show the banner. This test locks the select behavior.

Pass command: the same command.

Commit: `feat: keep the remote menu usable when the master link is down`

### Task 42. Button debounce

- [ ] Files: `common/buttons.py`, `tests/test_buttons.py`.

Failing test: `Debouncer(hold_ms=30)`. Sample Up pressed at t=0, still pressed at t=29, released at t=40. `events()` returns one `Press("up")` and no second event. A new press at t=100 returns a second `Press("up")`. Noise that is high for 10 ms and low again returns no event.

Fail command: `python3 -m pytest tests/test_buttons.py::test_one_press_after_30_ms -q`

Also `test_bounce_shorter_than_hold_is_ignored`.

Implementation: levels are active low in the raw mask, but the debouncer sees already-decoded names from a helper `changes(previous_mask, current_mask, names)`. Keep the raw mask helper and the timer separate so tests pass names and timestamps. No sleep.

Pass command: `python3 -m pytest tests/test_buttons.py -q`

Commit: `feat: debounce button presses`

### Task 43. Errors carry source and nature

- [ ] Files: `common/errors.py`, `tests/test_errors.py`.

This task creates only `common/errors.py` and the tests for `make_error`, `propagate`, and `banner`. The timed-out STA frame and the master LED are task 65, which runs after tasks 46, 53, and 64. That split is why this file list does not include `remote/tasks.py`.

Failing test: `make_error(ErrorCode.DATA_CORRUPTED, source="atu")` has `.nature == "Data Corrupted"` and `.source == "atu"`. `propagate([atu_error])` returns the same error wrapped with `.path == ("atu", "remote", "master")`. A local error `source="remote"` has `.local is True`. A link error `COMMUNICATION_LOST` has `.system is True`. `banner(error)` for communication lost is `Communication Lost`. `banner` for hot switch is `Hot switch`. `banner` for relay fault is `Relay fault`. The five spec nature strings from task 19 stay: `Failed to Execute Command`, `Data Not Available`, `Resource offline`, `Communication Lost`, `Data Corrupted`. `RESOURCE_OFFLINE` is code 3.

Fail command: `python3 -m pytest tests/test_errors.py::test_error_keeps_source_and_nature -q`

Implementation: dataclass `Fault`. System codes are `COMMUNICATION_LOST`, `HOT_SWITCH`, `RELAY_FAULT`, `RESOURCE_OFFLINE`. The others are local. Propagation does not drop the original nature. Do not add `emit_atu_offline` here.

Pass command: `python3 -m pytest tests/test_errors.py::test_error_keeps_source_and_nature -q`

Commit: `feat: propagate errors with a source and a nature`

### Task 44. Cooperative scheduler

- [ ] Files: `common/scheduler.py`, `tests/test_scheduler.py`.

Failing test: three tasks append their names. `run_once(tasks, interrupt=isr, watchdog=feed)` calls the interrupt task four times, each user task once, and `feed` once. A task that raises `RuntimeError` is caught, appended to `errors`, and the later tasks still run. A task that raises `RelayFault` is re-raised after the error is recorded. `run_once` does not call `time.sleep`.

Fail command: `python3 -m pytest tests/test_scheduler.py::test_interrupt_task_runs_four_times -q`

Also `test_task_exception_does_not_stop_the_loop` and `test_relay_fault_escapes`.

Implementation: `run_once` only. Import `RelayFault` from `common.errors`. Do not define it here. Task 64 builds the remote and master task lists and is the only place that calls `run_once` from `main`. No allocation inside the interrupt callable beyond what the test's ISR itself does. The runner does not build a new task list on each call. It iterates the list it was given. The import is the P-008 edit. The four interrupt passes and the watchdog call stay as this task's tests describe them.

Pass command: `python3 -m pytest tests/test_scheduler.py -q`

Commit: `feat: run cooperative tasks and an interrupt pass`

### Task 45. Fixed RX ring

- [ ] Files: `common/hal.py`, `tests/test_ring.py`.

Failing test: `ByteRing(8)`. Push 1, 2, 3. Pop returns them in order. Push 8 bytes into an empty ring, then one more. `overflow` is true and the oldest byte is gone. `push` of a single int does not allocate a `list` or `bytes` that the test can see: the storage attribute is a `bytearray` of length 8 before and after overflow. Importing `common.hal` leaves `sys.modules` without `machine`. `note_rx_byte(ring, flags, 0x41)` appends `0x41` and sets `flags.rx_pending`. It does not call `decode_frames`. `drain_rx(ring, flags)` returns the stored bytes and clears `flags.rx_pending`.

Fail command: `python3 -m pytest tests/test_ring.py::test_ring_drops_oldest_when_full -q`

Also `test_isr_only_sets_the_flag_and_stores_the_byte`.

Implementation: head and tail indexes. `hal.py` module comment explains the `try: import machine` / `except ImportError` at the top. `machine` stays None on the host. `ByteRing` does not import it. `note_rx_byte` is the only function a UART interrupt handler may call.

Pass command: `python3 -m pytest tests/test_ring.py -q`

Commit: `feat: buffer UART bytes in a fixed ring`

### Task 46. Apply an antenna command, then commit

- [ ] Files: `remote/tasks.py`, `tests/test_apply_antenna.py`.

Failing test: `apply_from_link(link_action, latch, state, power)` where the action is AT2, power is 0.2 W and fresh, state antenna is 1. After the call the latch is `0b0010`, `state.antenna` is 2, `state.previous.antenna` is 1, and the returned reply kind is `ack`. A second call with forward 5.0 W fresh returns kind `err` and code `HOT_SWITCH`, and the latch stays `0b0010`. `state.antenna` stays 2.

Fail command: `python3 -m pytest tests/test_apply_antenna.py::test_at2_commits_after_the_coil_moves -q`

Also `test_hot_switch_does_not_commit` and `test_relay_fault_rolls_back_and_opens_every_coil`. For the fault test, the fake latch reads `0b0011` after the target write. The call returns kind `err` with `RELAY_FAULT` and does not raise. The latch ends at 0. `state.antenna` is 0 and `state.relay_mask` is 0. `state.previous` still holds the antenna from before the attempt, for the log. The test asserts the latch was not written back to that previous mask.

`test_relay_fault_class_lives_in_errors`: a source scan of `common/`, `master/`, and `remote/` finds `class RelayFault` only in `common/errors.py`.

Implementation: call `apply_antenna_command`. On None, `commit` the new antenna and `relay_mask`, then return ack. On `HOT_SWITCH`, do not commit. On `RelayFault`, do not reapply `state.previous`. Call `safe_off(latch, "fault")`, then set `state.antenna` and `state.relay_mask` to 0. Leave `state.previous` as it was. Pass a fake sleep so the test does not wait 100 ms of real time. The delay value passed in is 100. `set_antenna` still contains the single-relay checks. This task only changes what the caller does after `RelayFault`.

Pass command: `python3 -m pytest tests/test_apply_antenna.py -q`

Commit: `feat: commit an antenna only after the coil move succeeds`

### Task 63. Dispatch link actions and menu handlers

- [ ] Files: `remote/tasks.py`, `master/tasks.py`, `tests/test_dispatch.py`.

This task calls the helpers from tasks 13, 22 through 28, 29, 33, 34, 40, and 46. It does not change their coil or codec rules.

Failing test file `tests/test_dispatch.py`. `dispatch_frame` feeds one `RemoteLink` frame, runs the hardware, and only then calls `finish` or `fail`.

- `test_at2_below_threshold_acks_after_the_latch`: forward 0.2 W, fresh sample, previous antenna 1. Event order is latch write, commit, then ACK. The latch ends at `0b0010`. The ACK payload byte is `0x12`. `finish` is not called before the latch write.
- `test_at2_above_threshold_is_hot_switch`: forward 5.0 W, fresh sample. The reply is ERR with payload `bytes([6, 2, 0x12])`. The latch is unchanged.
- `test_at0_below_threshold_opens_every_coil`: forward 0.2 W, latch starts at `0b0010`. After the call the latch is 0 and the ACK payload byte is `0x10`.
- `test_f86_opens_coils_at_50_w`: start at antenna 2 and `relay_mask` `0b0010`, forward 50.0 W. `safe_off` runs. The latch is 0, `state.antenna` is 0, and `state.relay_mask` is 0. `state.previous` still shows antenna 2. The ATU write buffer does not contain `{"Reset":true}`. The ACK payload byte is `0x35`. Do not write the previous mask back to the latch. Boot still starts from a fresh `LinkState` and is not this path.
- `test_rst_opens_coils_and_resets_the_tuner`: the same starting antenna and mask, forward 50.0 W. After the call, antenna, `relay_mask`, and the latch are 0. `state.previous` still shows antenna 2. The ATU write buffer contains `b'{"Reset":true}\n'`. The ACK payload byte is `0x33`.
- Serial mode, one test each, named `test_serial_byp0`, `test_serial_byp1`, `test_serial_am0`, `test_serial_am1`, `test_serial_tun`, `test_serial_sta`, `test_serial_tup`, `test_serial_tdn`, `test_serial_tsc`, `test_serial_tsl`, `test_serial_tst1`, and `test_serial_tst0`. Each mode and tune command except TST0 and TST1 writes the matching frozen outbound bytes, then an ACK. From step 0, TUP writes `{"RelayI":1}\n`, TDN writes `{"RelayI":0}\n`, TSC keeps step 0 and writes `{"RelayC":128}\n`, TSL keeps step 0 and writes `{"RelayI":0}\n`. `test_serial_tst1` writes no UART bytes, sets test mode active, and ACKs `0x26`. `test_serial_tst0` writes `b'{"Reset":true}\n'`, clears active, and ACKs `0x25`. TST0 and TST1 do not go through the `encode_command` dict from task 29. The `RelayI` and `RelayC` expectations, including TSC keeping the step and the next TUP sending `RelayC` 130, stay in task 33.
- Fallback mode: `test_fallback_tune_presses_and_writes_nothing`, and the same for BYP0, BYP1, AM0, and AM1. Each returns the press list from task 34 and leaves the ATU buffer empty, then ACKs. `test_fallback_tup_is_data_not_available` covers TUP, and the same assertion covers TDN, TSC, TSL, TST0, and TST1: ERR payload byte 0 is `DATA_NOT_AVAILABLE` (2), no press, no UART bytes. STA in fallback is the same error, because task 34 has no status to return.
- `test_master_menu_tune_enqueues_tun`: select the master menu leaf Tune. The master queue gains `Command.TUN`.
- `test_remote_menu_at4_with_link_down`: `link_up` is false. Select remote Antenna 4. The latch becomes `0b1000`. No master poll bytes are produced. Task 66 covers the other handler names. Leave these two tests as they are.
- `test_tune_opto_is_high_for_400_ms` in `tests/test_fallback.py`: no `time.sleep`. Fallback `TUN` drives only GPB4 high at `now_ms` 0, and `service_optos(400)` leaves it low. `AM0` holds only GPB5 and `service_optos(80)` clears it. `BYP1` holds only GPB6 and `service_optos(80)` clears it. `RST` holds GPB4 until 100 ms. A second `AM0` does not pulse. Serial-mode `TUN` writes `b'{"Tune":true}\n'` and leaves GPB4, GPB5, and GPB6 unchanged. Fallback TST, TUP, TDN, TSC, TSL, and STA still return `DATA_NOT_AVAILABLE` and do not pulse. Durations stay 400, 100, and 80. Task 34's press lists stay. Task 64 is what calls `service_optos` from every remote `run_once`. That later task extends this test to two `run_once` calls. This task's pass command calls `service_optos` directly so it can pass before the loop exists.

Fail command: `python3 -m pytest tests/test_dispatch.py::test_rst_opens_coils_and_resets_the_tuner tests/test_dispatch.py::test_f86_opens_coils_at_50_w tests/test_dispatch.py::test_serial_tst1 tests/test_dispatch.py::test_serial_tst0 tests/test_fallback.py::test_tune_opto_is_high_for_400_ms -q`

The earlier dispatch tests still fail first until `dispatch_frame` exists. Run the file as well.

Implementation: `dispatch_frame` in `remote/tasks.py` is the frame caller. Antenna actions call `apply_from_link` and `finish` only after it returns ack. Hot switch calls `fail` and does not `finish`. F86 and RST call `safe_off` even at 50 W, then set `state.antenna` and `state.relay_mask` to 0 and leave `state.previous` unchanged. They do not copy the previous mask onto the latch. RST then sends `b'{"Reset":true}\n'`. F86 does not. Serial BYP, AM, TUN, STA, TUP, TDN, TSC, and TSL call `encode_command` or `TestMode`. Serial TST1 and TST0 call `TestMode` only, not `encode_command`. Fallback calls `press_for` and `drive_opto(presses, olat, now_ms)` on the scheduler clock. `drive_opto` sets one bit and clears it when `now_ms` passes the A11 duration. Serial mode does not call `drive_opto`. The full handler map is task 66, which is why this task still only names `tun` and link-down `at4` for menus.

Pass command: `python3 -m pytest tests/test_dispatch.py tests/test_fallback.py::test_tune_opto_is_high_for_400_ms tests/test_test_mode.py::test_tst1_enters_test_mode_without_json -q`

Commit: `feat: dispatch antenna, tuner, and menu commands`

### Task 47. Link loss does not move relays

- [ ] Files: `remote/tasks.py`, `master/tasks.py`, `tests/test_link_loss.py`.

Failing test: remote latch is antenna 3. `on_link_lost(remote_state, latch)` sets `remote_state.banner` to `Communication Lost`, leaves `remote_state.antenna` at 3, and does not write the latch. Master `on_link_lost(master_state)` sets the same banner and does not grow a list of outbound antenna commands.

`test_communication_lost_banner_fits_the_panel`: `render_banner("Communication Lost")` returns `("Communication", "Lost", "", "")`. Each string is at most 16 characters. `" ".join(line for line in lines if line) == "Communication Lost"`. `on_link_lost` sets that banner and `link_up` false before `publish`. `publish(state, panel)` then shows those lines. A state with an empty banner and `link_up` true shows `screen_lines`, not the banner.

`test_hot_switch_banner_shows_while_the_link_is_up`: `link_up` is true and `banner` is `Hot switch`. `publish(state, panel)` shows `("Hot switch", "", "", "")`. The same `render_banner` wraps every spec nature string on spaces into four lines of at most 16 characters: `Failed to Execute Command` becomes `("Failed to", "Execute Command", "", "")`, `Data Not Available` becomes `("Data Not", "Available", "", "")`, `Resource offline` is 16 characters and is line 1 alone, and `Data Corrupted` is line 1 alone. Do not change the `Communication Lost` split.

Fail command: `python3 -m pytest tests/test_link_loss.py::test_link_loss_keeps_antenna_three tests/test_link_loss.py::test_communication_lost_banner_fits_the_panel tests/test_link_loss.py::test_hot_switch_banner_shows_while_the_link_is_up -q`

Implementation: both link-loss functions only set the banner and `link_up = False`. They do not write the latch and do not call `set_antenna` or `force_all_off`. No import of the other board's package. One function, `publish(state, panel)`, calls `show_lines`. If `state.banner` is non-empty, the lines are `render_banner(state.banner)`. If the banner is empty, the lines are `screen_lines`. `publish` does not look at `link_up`. The caller sets the banner first. There is no `publish(reading, panel)`. Task 51's panel test uses this signature. This replaces the earlier two-signature wording. The latch assertion in this task is unchanged.

Pass command: `python3 -m pytest tests/test_link_loss.py::test_link_loss_keeps_antenna_three tests/test_link_loss.py::test_communication_lost_banner_fits_the_panel tests/test_link_loss.py::test_hot_switch_banner_shows_while_the_link_is_up -q`

Commit: `feat: keep the current antenna when the RS485 link drops`

### Task 48. Master and remote simulator

- [ ] Files: `tests/test_simulator.py`, `master/tasks.py`, `remote/tasks.py`.

Failing test: `run_exchange()` wires `MasterLink` and `RemoteLink` through two `bytearray` queues, no sockets. Script: master queues AT2. After `step()` calls, the remote latch reads `0b0010` and the master log contains `RX ACK AT2`. Then the master queues TUN. The fake ATU port receives `b'{"Tune":true}\n'`. The test feeds a multiline status object with `Forward` 10.0, `Power` 9.0, `SWR` 1.10, `Auto` true, `Bypass` false, and `efficency` 90, using the brace rules in Frozen ATU JSON. After the status handshake, `screen_lines` on the master reading is exactly `("10.0W          .", "1.10", "9.0W", "90%")`. `test_at2_then_tune_against_fake_atu` names that one screen. Line 3 is the `Power` field. It is not 10.0 times 0.90.

Fail command: `python3 -m pytest tests/test_simulator.py::test_at2_then_tune_against_fake_atu -q`

Implementation: `run_exchange` and `step` call `maybe_poll`, `drain_rs485`, `poll_atu`, and `publish_display` from task 64. They do not keep a second function that writes RS485 bytes. The fake ATU is a `bytearray`, not a thread and not a socket. Use `now_ms` values that satisfy the poll timer. Do not open a serial port. The expected four-line screen in this task stays as written above. Line 3 is `Power`.

Pass command: the same command.

Commit: `feat: simulate a master, a remote, and a ukoda tuner`

### Task 49. Config pins and tunables

- [ ] Files: `master/config.py`, `remote/config.py`, `tests/test_config.py`.

Failing test: import both configs. The shared names `I2C_SDA`, `I2C_SCL`, `RS485_TX`, `RS485_RX`, `RS485_BAUD`, `ATU_TX`, `ATU_RX`, `ATU_BAUD`, `MCP_INTA`, `MCP_INTB`, `OLED_ADDR`, `MCP23017_ADDR` are equal across the two modules. The set of GPIO integers in both modules does not include 23, 24, 25, or 29. `remote.config.RELAY_DELAY_MS == 100`, `HOT_SWITCH_WATTS == 1.0`, `HOT_SWITCH_ENABLED is True`, `POLL_MS == 200`, `ATU_BAUD == 4800`, `RS485_BAUD == 115200`, `ATU_MODE == "serial"`. Also require `REPLY_TIMEOUT_MS == 500`, `REPLY_TRIES == 3`, `MISS_LIMIT == 5`, `ATU_TIMEOUT_MS == 500`, `ATU_TRIES == 3`, `TUNE_TIMEOUT_MS == 30000`, `POWER_STALE_MS == 1000`, `INDUCTOR_COUNT == 7`, `CAPACITOR_COUNT == 7`, `WATCHDOG_MS == 3000`, and `remote.config.REMOTE_SILENCE_MS == 2000`. Master button names equal the decision 5 list. Remote button names equal the decision 6 list. OLED address is `0x3C` and MCP address is `0x20`. These names are here because task 64 reads them and must not copy the numbers as literals. `REMOTE_SILENCE_MS` is assumption A3.

Fail command: `python3 -m pytest tests/test_config.py::test_shared_pins_match_and_wireless_gpios_are_free -q`

Also `test_timeouts_and_button_names`.

Implementation: every constant has a comment on the line above it saying what to change. `ATU_TX` and `ATU_RX` on the master are commented as reserved, unused on that board.

Pass command: `python3 -m pytest tests/test_config.py -q`

Commit: `feat: put pins, timeouts, and button maps in config`

### Task 50. MCP23017 direction, pull-up, and latch

- [ ] Files: `common/mcp23017.py`, `tests/test_mcp23017.py`.

Failing test, exact API:

- `write_iodir(port_a=0xFF, port_b=0x1F)` writes register `0x00` then `0x01`.
- `write_pullups(port_a=0xFF, port_b=0x1F)` writes `0x0C` and `0x0D`.
- `write_olat(port_a, port_b)` writes `0x14` and `0x15`.
- `read_olat()` reads `0x14` and `0x15` and returns both bytes.
- `enable_interrupts()` writes GPINTENA `0x04` and GPINTENB `0x05` with the input mask, and writes IOCON `0x0A` with `0x04` so INT is open drain.

Fail command: `python3 -m pytest tests/test_mcp23017.py::test_olat_write_uses_the_latch_registers -q`

Also test IODIR and the interrupt enable.

Implementation: those register addresses only. The remote relay latch uses port B bits 0..3, so `RelayLatch` in this same task adapts `read_olat`/`write_olat` to the 4-bit mask `set_antenna` expects. `RelayLatch.read` returns the low 4 bits of OLATB. `RelayLatch.write` changes only those bits and leaves GPB4..GPB6, the opto bits, as they were.

Pass command: `python3 -m pytest tests/test_mcp23017.py -q`

Commit: `feat: drive the MCP23017 latch for relay readback`

### Task 51. SSD1306 init and one character

- [ ] Files: `common/ssd1306.py`, `tests/test_ssd1306.py`.

Failing test: `SSD1306(FakeI2C(), 0x3C)`. `init()` writes `0x8D` then `0x14` (charge pump on), and still writes display-off `0xAE` and display-on `0xAF`, all to address `0x3C` with control byte `0x00` on the command writes. `draw_char(0, 0, "A")` sets an 8 by 8 block in page 0 that is not all zeros. `show_lines(("100.0W", "1.15", "1.25uH", "150pF"))` puts line 2's glyphs on page 1. The charge-pump bytes are required or the panel stays blank. Addresses `0x3C` and `0x20` stay as frozen.

Fail command: `python3 -m pytest tests/test_ssd1306.py::test_init_turns_the_panel_on -q`

Also `test_letter_a_is_not_blank` and `test_publish_sends_screen_lines`. `publish(state, panel)` is the only signature, from task 47. The test passes a state with an empty banner, forward 5.0, SWR 1.15, 1250 nH, 150 pF, auto false, bypass false, order `LC`, and efficiency None. `show_lines` receives that L/C screen, and line 1 ends with a space. There is no `publish(reading, panel)`. This edit matches the one `publish` contract. The banner cases stay in task 47.

Implementation: `init` writes `0x8D`, `0x14`, `0xAE`, and `0xAF` to `0x3C`. A built-in 8x8 glyph table covers `0-9`, `.`, `%`, `_`, space, `A-Z`, and `a-z`. The lowercase letters are required by the frozen menu labels, including `off`, `up`, `down`, and `tuner`, so `show_lines` does not raise `ValueError` when task 53 draws the menu. Include the letters in `Communication` and `Lost`. Missing glyphs raise `ValueError`. 128 by 64, four text rows on pages 0..3. No third-party driver. The charge-pump bytes are the P-028 edit. The glyph set is unchanged apart from that init sequence.

Pass command: `python3 -m pytest tests/test_wiring.py::test_remote_boot_opens_uarts_from_config tests/test_ssd1306.py::test_init_turns_the_panel_on -q`

The wiring test is task 64. Until that file exists, this task's gate is `python3 -m pytest tests/test_ssd1306.py::test_init_turns_the_panel_on -q`. After task 64, the paired command must pass. The init test still requires `0x8D`, `0x14`, `0xAE`, and `0xAF`.

Commit: `feat: draw tuner text on an SSD1306`

### Task 52. Boot order and import boundary

- [ ] Files: `remote/main.py`, `master/main.py`, `common/hal.py`, `tests/test_boot.py`, `tests/test_imports.py`.

Failing test: `boot_remote(latch, events)` appends `relays_off` before `watchdog`. `events == ["relays_off", "watchdog"]`. `boot_master(events)` appends only `watchdog`. Importing `master.main`, `remote.main`, `master.tasks`, `remote.tasks`, `remote.relays`, and `remote.atu_link` does not put `machine` in `sys.modules`. A source scan of every `.py` file under `common/`, `master/`, and `remote/` finds `import machine` only in `common/hal.py`. Neither tree's source contains `import remote` inside `master/` or `import master` inside `remote/`.

Fail command: `python3 -m pytest tests/test_boot.py::test_remote_boot_clears_relays_first -q`

Also `test_machine_import_stays_inside_hal`.

Implementation: `hal.start_watchdog(timeout_ms)` records the request and, when `machine` is None, does not raise. `boot_remote` calls `safe_off(latch, "boot")` then `hal.start_watchdog(3000)`. A watchdog reset starts the Pico again, so it enters `boot_remote` with whatever coils the expander still holds. The test starts the latch at `0b0100` and asserts it is 0 before the watchdog event. Do not write the repeating task list in this task. Task 64 is the superloop, which is why `main` here only defines `boot_remote`, `boot_master`, and the `if __name__ == "__main__"` guard. The boot tests call `boot_remote` directly so they do not loop. The existing boot and import tests stay.

Pass command: `python3 -m pytest tests/test_boot.py tests/test_imports.py -q`

Commit: `feat: clear the relay latch before the watchdog starts`

### Task 53. Wire buttons, LEDs, and the local menu into the tasks

- [ ] Files: `master/tasks.py`, `remote/tasks.py`, `tests/test_buttons_to_commands.py`.

Failing test: `master_on_press("tune", queue)` with the menu closed appends `Command.TUN`. `master_on_press("antenna", queue)` from a last antenna of 1 appends AT2. From 4 it appends AT1. It never appends AT0. `master_on_press("bypass", queue)` appends BYP1 when bypass is false and BYP0 when bypass is true. `master_on_press("am", queue)` appends AM0 when auto is false and AM1 when auto is true. `remote_on_press("select", menu, local_queue)` with the remote menu open on Antenna 1 appends `at1` even when `link_up` is false. LED helper `leds_for(link_up=False, fault=True, auto=True, bypass=False, rf=True)` returns Link OK false, Error true, Auto Mode true, Bypass false, RF Present true.

`test_menu_button_draws_the_highlighted_row`: the Menu button calls `open_menu`. Up, Down, Left, and Right call those menu methods. Select calls `select`. The render writes at most four labels. Each label is at most 16 characters. The highlight row is the current item. Opening the menu and pressing Down changes which label is highlighted on the panel. When the current level has more than four items, the window moves so the highlighted item stays visible. Exit Menu clears the menu, and the next `publish` is the tuner screen from `screen_lines`. A closed menu still maps Tune to `Command.TUN`. Frozen labels and handler names stay as written. Select on a parent still enters the child, which task 40 already tests.

`test_link_loss_sets_the_error_led_bit`: a fake OLAT. After `on_link_lost`, master GPB2 Link OK is low and GPB3 Error is high. After a fresh forward power of 1.1 W, GPB6 RF Present is high. At 1.0 W it is low. Auto Mode and Bypass follow the state flags. The remote write sets GPA5 Link OK and GPA6 Error only and does not modify GPB0 through GPB3. The frozen MCP bit map is unchanged.

Fail command: `python3 -m pytest tests/test_menu.py::test_menu_button_draws_the_highlighted_row -q`

Also run `python3 -m pytest tests/test_buttons_to_commands.py::test_tune_button_queues_tun tests/test_buttons_to_commands.py::test_link_loss_sets_the_error_led_bit -q` before the implementation. Those fail first too.

Implementation: `on_press` binds the five menu keys only while the menu is open. Tune, Antenna Select, A/M, and Bypass keep the closed-menu behavior above. `render_menu(menu)` returns at most four strings and a highlight index. `write_leds(state, olat)` writes `leds_for` onto the frozen LED bits. Relay bits stay inside `RelayLatch`. `publish_display` on both loops calls `write_leds`. This task adds that call. Task 64's task list already names `publish_display`.

Pass command: `python3 -m pytest tests/test_menu.py::test_menu_button_draws_the_highlighted_row tests/test_buttons_to_commands.py::test_tune_button_queues_tun tests/test_buttons_to_commands.py::test_link_loss_sets_the_error_led_bit -q`

Commit: `feat: map master and remote buttons onto commands`

### Task 64. Remote and master superloop

- [ ] Files: `remote/main.py`, `master/main.py`, `remote/tasks.py`, `master/tasks.py`, `common/hal.py`, `tests/test_main_loop.py`, `tests/test_wiring.py`, `tests/test_fallback.py`.

Task 44's `run_once`, task 45's ring, task 47's banner split, task 48's four-line tuple, task 10's idle timing and sequence wrap, and task 52's relays-off-before-watchdog order stay as those tests describe them. This task adds the lists, the buses, and the `main` call.

Failing tests, each written first:

- `test_remote_run_once_drains_and_feeds`: build the remote list with `build_remote_tasks`. Put one AT2 frame in the RS485 RX ring. Forward power is 0.2 W and fresh. One `run_once` drains that frame, moves the latch to `0b0010`, calls the ATU poll once, calls `publish` once, turns one debounced press into one sampled event, and calls the watchdog feed once.
- `test_master_run_once_drains_and_feeds`: the master twin. The RS485 RX ring holds an ACK of HHH. One `run_once` drains it, calls `publish` once, samples one debounced press, and feeds the watchdog once. The master has no relay latch.
- `test_idle_poll_loss_does_not_move_relays`: the master's miss counter crosses `miss_limit` inside `run_once`. `on_link_lost` is called. The spies for `set_antenna` and `force_all_off` stay at zero calls.
- `test_queued_at2_is_sent_instead_of_hhh`: with an empty queue, one idle `run_once` emits HHH. With `Command.AT2` queued and no reply outstanding, the bytes are an AT2 frame, not HHH. After the matching ACK, the next idle poll is HHH again.
- `test_remote_silence_sets_communication_lost`: antenna 3 is selected. No accepted frame for 1999 ms leaves antenna 3, does not write the latch, and does not set the banner. At 2000 ms, `on_link_lost` runs, the banner is `Communication Lost`, and the latch is still antenna 3. The next valid frame clears the banner and sets `link_up` true.
- `test_atu_status_is_committed_and_sent`: UART1 bytes carry `Forward` 10.0, `Power` 9.0, `SWR` 1.10, `efficency` 90, and `Order` `LC`, in the multiline shape from task 30. `poll_atu` updates the remote `LinkState` through `commit`, including `order` and `power_sample_ms` equal to that `now_ms`. The next idle poll completes RS, RR, SND, and RCVD. The SND payload is 13 bytes and flags bit 6 is clear. After RCVD, master `LinkState.order` is `LC` and the master screen is the task 48 tuple `("10.0W          .", "1.10", "9.0W", "90%")`. The same watts with `Order` `CL` still show that tuple, because line 3 is `Power`, flags bit 6 is set, and master `LinkState.order` is `CL`. A payload with no efficiency, inductance 1250 nH, capacitance 150 pF, and `Order` `CL` shows C on line 3 and L on line 4, and master `order` is `CL`. The same L and C with `Order` `LC` and no efficiency shows L on line 3 and C on line 4. Do not change task 37's local `screen_lines` cases, task 20's stored field, task 30's JSON parse, or the task 48 tuple.
- `test_remote_boot_opens_uarts_from_config` in `tests/test_wiring.py`: inject a fake `machine` with `hal.bind`. `boot_devices("remote")` opens UART0 at `RS485_BAUD` on the RS485 pins, UART1 at `ATU_BAUD` on the ATU pins, and I2C on `OLED_ADDR` and `MCP23017_ADDR`. `boot_devices("master")` does not open UART1. GPIO 23, 24, 25, and 29 are unused. `MasterLink` uses `POLL_MS`, `REPLY_TIMEOUT_MS`, `REPLY_TRIES`, and `MISS_LIMIT`. `AtuLink` uses `ATU_TIMEOUT_MS`, `ATU_TRIES`, and `TUNE_TIMEOUT_MS`. The relay delay, watchdog, hot-switch threshold, enable flag, stale window, `ATU_MODE`, `INDUCTOR_COUNT`, and `CAPACITOR_COUNT` are the config names. Changing `POLL_MS` on the config object changes the `MasterLink` the test reads. Those numbers are not literals in `main`. Importing the packages does not put a real `machine` in `sys.modules`. The test's fake is injected only through `hal.bind`. Before either board's first `run_once`, `boot_devices` calls `SSD1306.init`, `write_iodir`, `write_pullups`, and `enable_interrupts`. Master `IODIRA` is `0xFF`. Master pull-ups are GPA0 through GPA7 and GPB0 and GPB1. Master `IODIRB` is `0x83`: GPB0 and GPB1 inputs, GPB2 through GPB6 outputs, and unused GPB7 left an input. Remote `IODIRA` is `0x9F`: GPA0 through GPA4 inputs, GPA5 and GPA6 outputs, unused GPA7 an input, with pull-ups only on GPA0 through GPA4. Remote `IODIRB` is `0x80`: GPB0 through GPB6 outputs, unused GPB7 an input. Interrupt enable matches those input bits. Pico GPIO numbers, MCP address `0x20`, and OLED address `0x3C` stay as frozen.
- `test_tune_opto_is_high_for_400_ms` in `tests/test_fallback.py`: this task replaces the direct `service_optos(400)` call from task 63 with two remote `run_once` calls. There is no `time.sleep` and no second command. After fallback `TUN`, only GPB4 is high at `now_ms` 0, and at `now_ms` 400 GPB4 is low. GPB5 follows the same pattern at 80 ms. GPB6 follows the same pattern at 80 ms. Serial-mode `TUN` still writes the Tune JSON and leaves GPB4, GPB5, and GPB6 unchanged. Task 63 may keep the direct `service_optos(400)` call so that task can pass before this loop exists.

Fail command: `python3 -m pytest tests/test_main_loop.py::test_queued_at2_is_sent_instead_of_hhh tests/test_fallback.py::test_tune_opto_is_high_for_400_ms -q`

Also run, and expect them to fail first, `python3 -m pytest tests/test_fallback.py::test_tune_opto_is_high_for_400_ms -q`, plus `test_remote_silence_sets_communication_lost`, `test_atu_status_is_committed_and_sent`, `test_remote_boot_opens_uarts_from_config`, and the three loop tests named above.

Implementation: `build_remote_tasks` returns `drain_rs485`, `poll_atu`, `service_optos`, `publish_display`, and `sample_buttons`. `service_optos` runs on every remote pass with the scheduler `now_ms` and is what clears a fallback opto bit when its A11 duration has elapsed. It does not start a new press. `build_master_tasks` returns `drain_rs485`, `maybe_poll`, `publish_display`, and `sample_buttons`. `maybe_poll` is the only RS485 sender. When the link is idle it transmits the oldest queued command. It transmits HHH only when that queue is empty. Task 48's `run_exchange` and `step` call this function and do not write frames themselves. `maybe_poll` calls `on_link_lost` when the miss count reaches `MISS_LIMIT`, and that branch does not call `set_antenna` or `force_all_off`. Remote `drain_rs485` calls `on_link_lost` when the last accepted frame is at least `REMOTE_SILENCE_MS` old, and a later accepted frame clears the banner and sets `link_up` true. UART0 and UART1 each have a `ByteRing`. Each UART interrupt handler may call only `note_rx_byte` on its own ring. `poll_atu` calls `drain_rx` on the UART1 ring, then `feed`. It does not parse JSON in the interrupt. On a parsed status it `commit`s `forward_w`, `antenna_w`, `swr`, `inductance_nh`, `capacitance_pf`, `efficiency_pct`, `auto`, `bypass`, `order`, and `power_sample_ms` from the same `now_ms`, then `notify_status(pack_status(...))`. `pack_status` sets flags bit 6 from `order` and stays 13 bytes, which is the task 09 layout. Master `drain_rs485` commits an unpacked SND into `LinkState` before `publish_display`. `publish_display` calls `publish` and `write_leds`. The MCP pin interrupt only sets `flags.mcp`. The interrupt callable inside `run_once` reads the expander only when that flag is set. `boot_devices(role)` calls `boot_remote` or `boot_master` from task 52 first, then opens the buses from config, calls `SSD1306.init`, `write_iodir`, `write_pullups`, and `enable_interrupts` with the masks in the boot test, and passes `WATCHDOG_MS` into `hal.start_watchdog`. Those four calls happen before the first `run_once`. `main`'s `__main__` block calls `boot_devices` and then repeats `run_once`. Tests call `boot_devices` after `hal.bind` and do not loop. `common/hal.py` remains the only module whose source imports `machine`.

Pass command: `python3 -m pytest tests/test_status_payload.py::test_status_payload_round_trip tests/test_main_loop.py::test_atu_status_is_committed_and_sent tests/test_wiring.py::test_remote_boot_opens_uarts_from_config tests/test_ssd1306.py::test_init_turns_the_panel_on tests/test_fallback.py::test_tune_opto_is_high_for_400_ms tests/test_main_loop.py::test_remote_run_once_drains_and_feeds -q`

Commit: `feat: run the remote and master task lists`

### Task 65. Deliver an ATU timeout to the master

- [ ] Files: `remote/tasks.py`, `master/tasks.py`, `tests/test_errors.py`.

This task follows tasks 46, 53, and 64. Task 43 already built `make_error`, `propagate`, and `banner`. Do not move those tests here.

Failing test `test_atu_timeout_becomes_master_err`: one remote `run_once` whose `AtuLink` has exhausted `ATU_TRIES` on STA queues an ERR frame with payload `bytes([3, 3, 0x04])`. The test does not call a helper named `emit_atu_offline`. The next master drain sets the master banner to `Resource offline` and turns the Error LED on. Until that frame is delivered, the master Error LED stays off.

`test_local_fault_stays_off_the_master_until_the_frame`: a local relay fault sets the remote banner to `Relay fault` and leaves the master Error LED off until the remote's ERR frame is delivered.

Fail command: `python3 -m pytest tests/test_errors.py::test_atu_timeout_becomes_master_err -q`

Also run `test_local_fault_stays_off_the_master_until_the_frame`. It fails first.

Implementation: `poll_atu` queues that ERR when `AtuLink` returns `RESOURCE_OFFLINE`. Master `drain_rs485` applies the ERR to the banner and the Error LED. The payload bytes and task 32's three `{"Status":true}\n` writes stay as already specified. The five spec nature strings stay in task 19.

Pass command: `python3 -m pytest tests/test_errors.py::test_atu_timeout_becomes_master_err tests/test_errors.py::test_local_fault_stays_off_the_master_until_the_frame -q`

Commit: `feat: show an ATU timeout on the master after the ERR frame`

### Task 66. Run every menu handler

- [ ] Files: `remote/tasks.py`, `master/tasks.py`, `tests/test_dispatch.py`.

Task 63 keeps its F86 and RST cases at 50 W, its serial and fallback byte lists, and its link-down `at4` latch result. This task adds the rest of the frozen handler names so task 63 does not grow.

Failing test `test_every_menu_handler_runs`: one assertion per handler. On the master, `at1` appends `AT1`, `at2` appends `AT2`, `at3` appends `AT3`, `at4` appends `AT4`, `at0` appends `AT0`, `tun` appends `TUN`, `am0` appends `AM0`, `am1` appends `AM1`, `byp1` appends `BYP1`, `byp0` appends `BYP0`, `tst1` appends `TST1`, `tst0` appends `TST0`, `tup` appends `TUP`, `tdn` appends `TDN`, `tsc` appends `TSC`, `tsl` appends `TSL`, `sta` appends `STA`, `rst` appends `RST`, and `f86` appends `F86`. `exit` appends nothing. On the remote, those handlers except `f86` act locally when `link_up` is true and when it is false. `REMOTE_MENU` has no Shutdown item, so remote `f86` is absent. Remote antenna handlers call `apply_antenna_command`. Remote `at4` changes the latch to `0b1000` in both link states. Remote tuner handlers use the same serial or fallback path as `dispatch_frame`. `exit` runs no command and does not write the latch. Every frozen handler name is one of those three outcomes.

Fail command: `python3 -m pytest tests/test_dispatch.py::test_every_menu_handler_runs -q`

Implementation: one dict from handler name to `Command` for the master queue. The remote function calls `apply_antenna_command` or `dispatch_frame` with the matching command. `exit` returns before either call.

Pass command: `python3 -m pytest tests/test_dispatch.py::test_every_menu_handler_runs -q`

Commit: `feat: run every menu handler on the master and the remote`

### Task 54. Docstrings and module comments

- [ ] Files: `tests/test_comments.py` and any module from earlier tasks that fails it.

Failing test: walk every function defined in `common`, `master`, and `remote`. Each has a non-empty `__doc__`. Each module's first statement is a string comment or the file starts with a `#` line. The test reads the source and requires the first non-empty line to start with `#`. `remote/atu_link.py` contains the AM0 sentence. `remote/relays.py` contains the phrase `only place a coil is turned on`.

Fail command: `python3 -m pytest tests/test_comments.py::test_modules_and_functions_are_explained -q`

Implementation: fill any missing module comment or docstring. Do not add functions only to satisfy the test.

Pass command: the same command.

Commit: `docs: explain each module and function for the operator`

### Task 55. Assumptions document

- [ ] Files: `docs/ASSUMPTIONS.md`, `tests/test_docs_assumptions.py`.

Failing test: the file starts with the eight client decision headings in order, each containing the assumed answer text `more than 1 W`, `Keep the current antenna`, `ukoda/ATU-100-remote`, `TST0/TST1`, `Antenna Select`, `5 buttons`, `100 ms`, and `GPIO 23, 24, 25 or 29`. Later sections contain the ids A1 through A21, the name `Forward`, and the names `REPLY_TIMEOUT_MS`, `REMOTE_SILENCE_MS`, `ATU_MODE`, and `common/hal.py`. A12 in that file says `Power` is antenna watts when efficiency is present and that antenna watts are not forward watts times efficiency. A21 says `order` is stored.

Fail command: `python3 -m pytest tests/test_docs_assumptions.py::test_client_decisions_are_first -q`

Implementation: copy decisions 1 through 8 from the PRD wording in the Assumptions section of this plan, then the engineering assumptions with where to change each one. Plain sentences.

Pass command: the same command.

Commit: `docs: record client decisions and the engineering assumptions`

### Task 56. Wiring document

- [ ] Files: `docs/WIRING.md`, `tests/test_docs_wiring.py`.

Failing test: the doc contains all of these strings: `GPIO 8`, `GPIO 9`, `GPIO 0`, `GPIO 1`, `GPIO 4`, `GPIO 5`, `GPIO 10`, `GPIO 11`, `0x3C`, `0x20`, `GPIO 23`, `GPIO 29`, `74AHCT1G125`, `2.2k`, `3.3k`, `RB1`, `RB2`, `RB0`, `yellow`, `white`, `VBUS`, `100k`, `Communication Lost` is not required here. It must contain `physical A/M and Bypass buttons are not usable` and `do not wire fallback optocouplers and the UART at the same time`.

Fail command: `python3 -m pytest tests/test_docs_wiring.py::test_wiring_names_the_level_shift -q`

Implementation, these facts, not a generic pin table:

- Pico 2 W GPIO 23 is wireless power-on, 24 is wireless SPI data, 25 is wireless SPI chip select, 29 is wireless SPI clock and VSYS sense. Do not connect them.
- U094 HY2.0-4P: black GND, red 5 V from Pico VBUS, yellow unit UART_RX to Pico GPIO 0, white unit UART_TX to Pico GPIO 1. Schematic `SCH_UNIT_ISO485` v1.1 level-shifts the Grove data pins for a 3.3 V host. No DE pin.
- Fit the supplied 120 ohm resistor across A and B at the remote unit only.
- PIC16F1938 on the EXT board runs at 5 V. RB1 is ukoda TXD (`LATB1`). RB2 is ukoda RXD (`PORTBbits.RB2`). PORTB inputs are Schmitt triggers, so a valid high is 0.8 times 5 V, which is 4.0 V. Pico 3.3 V is not a valid high into RB2, and 5 V out of RB1 exceeds the Pico absolute maximum.
- Up path: Pico GPIO 4 into a 74AHCT1G125 powered from the tuner 5 V rail. Output through 1k to RB2. 74AHCT treats 3.3 V as a high.
- Down path: 2.2k from RB1 to Pico GPIO 5, 3.3k from GPIO 5 to ground. That is 3.0 V at the Pico.
- Common ground between the Pico and the tuner logic ground.
- Relay opto inputs have a 100k pull-down so a floating expander cannot energize a coil during boot.
- Fallback optos, only when `ATU_MODE` is `fallback`: GPB4 across Tune (RB0 to ground), GPB5 across A/M (RB1 to ground), GPB6 across Bypass (RB2 to ground), 330 ohm into each opto LED, active high. Serial mode uses the UART parts instead and leaves those opto drivers unpopulated.
- MCP23017 RESET held high with 10k to 3.3 V. INTA and INTB each have 10k to 3.3 V. I2C pull-ups: use the ones on the Adafruit board and the OLED. Do not add a second pair.
- Master and remote Pico headers match. Expander bit maps are the Frozen pins lists.

Pass command: the same command.

Commit: `docs: specify Pico, U094, MCP23017, OLED, and ATU-100 wiring`

### Task 57. Protocol document

- [ ] Files: `docs/PROTOCOL.md`, `tests/test_docs_protocol.py`.

Failing test: the doc contains the known frame `7e010201110047517f`, the CRC name `CRC-16/CCITT-FALSE`, every mnemonic in the command table, the sentence `The remote does not transmit until the master polls`, and the RS to RR to SND to RCVD order.

Fail command: `python3 -m pytest tests/test_docs_protocol.py::test_protocol_doc_has_the_at1_frame -q`

Implementation: byte layout, the worked AT1 example, the status payload layout, retries, and the handshake explanation from Frozen protocol. One worked ERR example for hot switch: payload `06 02 11`.

Pass command: the same command.

Commit: `docs: describe the RS485 frame and the poll handshake`

### Task 58. ATU link document and firmware notes

- [ ] Files: `docs/ATU_LINK.md`, `atu100_firmware/README.md`, `tests/test_docs_atu.py`.

Failing test: both files contain `ATU-100_remote_PIC16F1938_20260412_1157.hex` and `4800`. `docs/ATU_LINK.md` contains `efficency`, `{"x":true}`, `RelayC` bit 7, and `Forward`. `atu100_firmware/README.md` contains `MPLAB X`, `XC8`, `docker.sh`, `pk2cmd`, `// REMOTE LINK`, and a unified diff that adds `json_int("Forward", g_i_Power, sft)` in `send_state`. It says the host tests do not compile the PIC.

Fail command: `python3 -m pytest tests/test_docs_atu.py::test_firmware_notes_pin_the_ukoda_hex -q`

Implementation: command map from Frozen ATU JSON. Limitations: one field per outbound message, blocking replies, commands ignored while tuning, local display EEPROM ignored, WIP. Inbound objects are multiline, as task 30 parses them. The diff is only that one `Forward` line, with the comment `// REMOTE LINK` on the line above it. Do not change the tuning algorithm. Fallback losses: no forward power, so no hot-switch interlock, no L/C test steps, no SWR or efficiency on the OLED. Build notes: upstream docker image from `zsteva/mplab-pic-xc8-builder`, `docker.sh`, then `make`, or MPLAB X with XC8. Flash only after a backup, command shape `pk2cmd -PPIC16F1938 -GF` for the readback. Do not put a hex file in the repo. Say that this host cannot run XC8, so the diff is documented and not compiled here.

Pass command: the same command.

Commit: `docs: record the ukoda map and the Forward field diff`

### Task 59. Flashing document

- [ ] Files: `docs/FLASHING.md`, `tests/test_docs_flashing.py`.

Failing test: the doc contains `v1.29.0`, `RPI_PICO2_W`, `mpremote`, `cp -r common`, `master/main.py`, `:main.py`, `BOOTSEL`, and `pk2cmd -PPIC16F1938 -GF`. It says to back up the original PIC hex before writing.

Fail command: `python3 -m pytest tests/test_docs_flashing.py::test_flashing_doc_names_the_firmware -q`

Implementation: hold BOOTSEL, copy the v1.29.0 Pico 2 W UF2, then the exact `mpremote` copies from assumption A18 for each board. PIC section: read the chip into a backup file first. The image to write is the pinned ukoda tree plus the `Forward` diff in `atu100_firmware/README.md`, built with MPLAB X and XC8 or the ukoda docker flow. Say that this host cannot run XC8, so the bench image is not produced here. Do not tell the operator that the untouched upstream hex reports forward watts above 1 W. This edit keeps task 59 consistent with assumption A12.

Pass command: the same command.

Commit: `docs: explain how to flash the Picos and the ATU-100`

### Task 60. Bench test plan

- [ ] Files: `docs/TEST_PLAN.md`, `tests/test_docs_bench.py`.

Failing test: the doc has three ordered headings `No RF`, `Dummy load`, and `Antennas`. The No RF section says all relays off at power-up and forbids a wattmeter reading requirement. The Dummy load section says low power and a dummy load before any antenna. The Antennas section says one relay at a time and a power above 1 W must be refused.

Fail command: `python3 -m pytest tests/test_docs_bench.py::test_bench_plan_starts_with_no_rf -q`

Implementation: step by step. No RF: power both Picos, confirm `Communication Lost` clears after the poll, select each antenna and confirm only one coil, press F86 and confirm all coils open, pull the RS485 plug and confirm the selected coil stays closed and both OLEDs show `Communication Lost`. Dummy load: 5 W or less into a dummy load, confirm the power text and that a change above 1 W is refused, then drop power and confirm the change is allowed. Antennas: one band, one antenna, then the other three, never two coils. Stop if the latch readback fails.

Pass command: the same command.

Commit: `docs: write the bench procedure from no RF up to antennas`

### Task 61. Customizing, project readme, summary

- [ ] Files: `docs/CUSTOMIZING.md`, `docs/README.md`, `SUMMARY.md`, `README.md`, `tests/test_docs_rest.py`.

Failing test: `docs/CUSTOMIZING.md` tells the operator how to add a command in `common/commands.py`, change a button in `master/config.py`, add a menu item in `common/menu.py`, and change `RELAY_DELAY_MS`. `docs/README.md` contains the words master, remote, RS485, and ATU-100, and it points at `docs/WIRING.md` and `docs/FLASHING.md`. Root `README.md` contains `docs/README.md` and is no longer only the line `antenna-project`. `SUMMARY.md` lists host tests as the verification that ran without hardware, names the ukoda hex as not flashed here, says a fork was required to add `Forward`, says that fork was not compiled here, and lists the eight client decisions as open for the client to confirm.

Fail command: `python3 -m pytest tests/test_docs_rest.py::test_root_readme_points_at_the_project_readme -q`

Also test the customizing names and the summary phrases in this task.

Implementation: short pages. The root README keeps a pointer only. Do not turn it into a second manual. `SUMMARY.md` is honest: no Pico, no PIC programmer, and no RF were available in the host run. It states the A12 fork in one sentence.

After those pages pass `python3 -m pytest tests/test_docs_rest.py -q`, run the host gate from this task, not from task 62:

```bash
python3 -m pytest tests -q
python3 -m compileall -q common master remote
```

Both must exit 0. `compileall` must not import hardware. If both pass, check this box and the task 62 box in this commit. Do not add an empty commit for task 62. If either command fails, leave the task 62 box unchecked and do task 62 before you consider the suite green. Commit the docs either way once `tests/test_docs_rest.py` passes. A red suite does not block that docs commit. Task 62 is the follow-up.

Pass command: `python3 -m pytest tests/test_docs_rest.py -q`

Commit: `docs: add the operator guide, the summary, and a README pointer`

### Task 62. Fix the host suite only if task 61's run failed

- [ ] Files: none new unless the host gate in task 61 exited nonzero.

Do not run the suite before task 61. Task 61 owns the first run. Start this task only when that run failed.

Failing test: the same two commands that failed at the end of task 61.

```bash
python3 -m pytest tests -q
python3 -m compileall -q common master remote
```

Fix the one failure in the module that owns it. Add the missing assertion to the existing test file if the failure is a real gap. Do not delete tests.

Pass command: the same two commands. Both exit 0.

Commit: `fix: close the host suite`

If task 61's run was already green, do not start this task and do not create a commit. The box was checked in the task 61 commit. A green suite does not add an empty commit.

## Coverage

| PRD item | Task |
| --- | --- |
| Frame, CRC, stuffing, bad frames | 01, 03, 04, 05, 06, 07, 08 |
| Every command byte | 02 |
| Poll, retry, sequence wrap, link loss, Communication Lost | 10, 11, 12, 47, 64 |
| RS, RR, SND, RCVD, RPT, STA, ACK, ERR | 09, 14, 15, 16, 19 |
| RST, RST RDY, F86 | 17, 18, 28, 63 |
| AT0..AT4 break-before-make, one coil, readback | 22, 23, 24, 25, 46, 63 |
| Boot, reset, watchdog, fault, all off | 28, 52, 64 |
| Hot switch, stale power, missing power, 1.0 W boundary | 26, 27, 63 |
| Link loss keeps the antenna | 47, 64 |
| ukoda JSON map, multiline parse, Forward field, half duplex, tune wait | 29, 30, 31, 32, 58 |
| Test mode RelayI and RelayC | 33, 63 |
| Fallback press times and lost features | 34, 58, 63 |
| Display formats, marker, efficiency screen | 35, 36, 37, 38, 39 |
| Menu, including link down | 40, 41, 63 |
| Buttons, LEDs, MCP23017 | 42, 50, 53 |
| Errors, source, nature, ATU offline | 19, 43, 65 |
| Menu handlers | 40, 41, 63, 66 |
| Scheduler, watchdog, ISR ring, superloop, buses | 44, 45, 52, 64 |
| State commit and rollback | 20, 21, 46 |
| Simulator | 48 |
| Config | 49 |
| SSD1306 | 51 |
| Docs and summary | 55 through 61 |
| Host suite | 62 |

## What the builder must not do

- Do not energize two relay bits in any function, including tests that drive a fake latch. The assertion is that the production function does not do it.
- Do not import `machine` outside `common/hal.py`.
- Do not add pip product dependencies, a web framework, or `uasyncio`.
- The only firmware edit is the `Forward` line in assumption A12. Do not fork any other ukoda behavior. Do not vendor the ukoda tree. Do not claim the host compiled XC8.
- Do not push, and do not open a pull request.
