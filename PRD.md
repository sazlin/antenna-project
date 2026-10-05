# PRD: Remote Antenna Switch and ATU-100 Control System

Approved product requirements. The original client Spec is `spec/Antenna_Switch_Project.pdf`. Where this PRD and the PDF disagree, this PRD wins (client decisions and spec errata below). The client is not available. Where the Spec is ambiguous, incomplete, or contradictory, make a sound engineering decision, make it configurable where practical, and record it in `docs/ASSUMPTIONS.md`. Do not stop to ask.

## Client context

The client is a radio amateur, not a professional programmer. He will read, maintain, and tweak this code himself. Clear structure and thorough comments are as important as functionality.

## Client decisions

These questions were sent to the client. Implement the assumed answer for each, make it easy to change, and list all of them at the top of `docs/ASSUMPTIONS.md` so the client can confirm or override them.

1. Hot-switch protection. Should the remote refuse an antenna change while transmitting?
   Assumed: Yes. Refuse with ERR whenever the ATU-100 reports more than 1 W forward power. Threshold and enable/disable in config. Only effective when the ATU-100 serial link is reporting power.
2. RS485 link loss. Keep the current antenna or switch all relays off?
   Assumed: Keep the current antenna selected and show "Communication Lost" on both displays. Dropping a relay under RF is the most damaging case for the contacts.
3. ATU-100 firmware basis. Use the existing open source serial firmware (github.com/ukoda/ATU-100-remote) instead of a new RA6/RA7 bit-bang link?
   Assumed: Yes. Build on ukoda/ATU-100-remote using Microchip's free MPLAB X IDE and XC8 compiler. The client has a PICkit 3 or similar. The original mikroC compiler needs a paid license because the firmware exceeds the free 2K-word limit.
4. Test mode. Is direct L/C relay control an acceptable replacement for the ATU-100's power-up Test mode?
   Assumed: Yes. TST0/TST1, TUP, TDN, TSC and TSL are implemented on the Remote Controller using the firmware's direct relay commands. No ATU-100 power cycling.
5. Master buttons and LEDs.
   Assumed: Buttons: Up, Down, Left, Right, Select (menu navigation), Tune, A/M, Bypass, Antenna Select, Menu. LEDs: Link OK, Error, Auto Mode, Bypass, RF Present. All mapped in `master/config.py`.
6. Remote buttons and LEDs.
   Assumed: 5 buttons (Up, Down, Left, Right, Select) driving a local menu for antenna select and ATU-100 control. 2 LEDs: Link OK, Error. Mapped in `remote/config.py`.
7. Relay break-before-make delay.
   Assumed: 100 ms, configurable. Coil flyback diodes can slow relay release to as much as 100 ms.
8. Pin assignments.
   Assumed: Identical pin assignments on both Picos, chosen by the implementer, never using GPIO 23, 24, 25 or 29 (used by the Pico 2 W wireless chip). Documented in `docs/WIRING.md`.

## Study first

1. The Spec (`spec/Antenna_Switch_Project.pdf`).
2. ukoda/ATU-100-remote (https://github.com/ukoda/ATU-100-remote): README, Guide.md, firmware source, and the Python control programs. Note its limitations: work in progress with modest testing; 4800 baud on RB1 (TXD) and RB2 (RXD); JSON messages; only the last received field is buffered, so send one field per message; replies are blocking, so treat the link as half duplex; other commands are ignored while tuning; local display settings are ignored.
3. Original ATU-100 firmware v3.2, EXT board: https://github.com/Dfinitski/N7DDC-ATU-100-mini-and-extended-boards (ATU_100_EXT_board folder) and its user manual. Use it to confirm exact display formats, when the post-tune power/efficiency screen appears, and button timing for the fallback mode.
4. Datasheets: Raspberry Pi Pico 2 W (RP2350), MCP23017, SSD1306, M5Stack RS485-ISO Unit U094, PIC16F1938.

## Spec errata (treat as corrections)

- "RS4485" means RS485.
- "AT22" in the bit-banging table means AT2.
- "BTP button" means the Bypass button.
- "CMC interference" means RF / common-mode interference.
- AM0 = Auto, AM1 = Manual as written (opposite polarity to BYP and TST). Keep this mapping and comment it.
- The Spec's RA6/RA7 bit-bang link is superseded by client decision 3. The ATU-100 link is now a hardware UART on the Pico.

## Repository layout

Adjust if justified and document why.

```
common/            shared MicroPython modules (copied to both Picos)
  protocol.py      RS485 framing, CRC, encode/decode, retries
  commands.py      command and error codes (single source of truth)
  state.py         current/previous state tables, commit, rollback
  scheduler.py     cooperative task loop
  mcp23017.py      I/O expander driver (inputs, outputs, interrupts)
  ssd1306.py       OLED driver
  display.py       line/char/scroll text API
  menu.py          5-button scrollable menu
  buttons.py       debounce and press events
  errors.py        error creation, propagation, display
master/            main.py, config.py, master tasks
remote/            main.py, config.py, relays.py, atu_link.py, button_emulation.py
atu100_firmware/   fork of ukoda/ATU-100-remote (only if changes are needed), unified diff vs upstream, build notes
tests/             pytest suite runnable on a PC with hardware mocks
docs/              see Documentation
```

## Requirements

### RS485 link (Master to Remote)

- Half-duplex via the U094 on a Pico UART. The Spec leaves the frame TBD: design it. Suggested fields: start byte, source, destination, sequence number, command, payload length, payload, CRC-16/CCITT, end byte. Framing must be robust to binary payloads and partial/corrupt frames.
- Avoid bus collisions: Master polls the Remote periodically (configurable, e.g. 200 ms); the Remote returns queued status changes and errors in its replies. Explain how the Spec's RS/RR handshake maps onto this.
- Implement every Master/Remote command in the Spec tables: ACK, HHH, RPT, STA, RS, RR, AT0 to AT4, TUN, BYP0/1, AM0/1, TST0/1, TUP, TDN, TSC, TSL, SND, RCVD, ERR, RST, RST RDY, F86. Use compact codes on the wire, mnemonics in logs and comments.
- Timeouts, retries, duplicate rejection via sequence numbers, link-loss detection, and "Communication Lost" on both displays. On link loss, follow client decision 2.

### Remote: antenna relays

- Four outputs, at most one active. All off at boot, reset, F86, watchdog restart, and unrecoverable fault.
- Sequence: deactivate current relay, wait the configured delay (decision 7), activate new relay, commit state, then send ACK.
- Enforce the single-relay rule in one function; read back the output latch to confirm.
- Hot-switch interlock per client decision 1.

### Remote to ATU-100 link

- Use the second Pico hardware UART at 4800 baud to the ATU-100's RB1 (TXD) and RB2 (RXD) pins, speaking the ukoda JSON protocol. Implement a robust driver in `remote/atu_link.py`: one field per message, wait for replies before sending again, timeouts, retries, and graceful handling of malformed JSON.
- Map Spec commands to ukoda messages: AM0/AM1 to "Auto", BYP0/BYP1 to "Bypass", TUN to "Tune", STA to "Status", RST to "Reset" or soft restart ("x") as appropriate. Implement TST0/TST1, TUP, TDN, TSC and TSL on the Remote using "RelayI" and "RelayC" (decision 4), tracking which bank is selected and the current step.
- Poll or receive status updates (power, SWR, L in nH, C in pF, Auto, Bypass, LC/CL order, efficiency) and convert them to the ATU-100 display formats.
- Firmware: use the ukoda hex as-is if it meets the needs. Fork and modify only if required (for example, if power below 10 W lacks the 0.1 W resolution the display format needs, or to report errors). Keep changes minimal, marked `// REMOTE LINK`, preserving the tuning algorithm. Builds must use MPLAB X with XC8; document the build and the ukoda docker build option. If you cannot compile, say so and keep changes conservative.
- Electrical: verify the logic levels on RB1/RB2 against the Pico's 3.3 V GPIO and specify level shifting or protection if needed. Note in the wiring guide that the ATU-100's physical A/M and Bypass buttons are no longer usable with this firmware.
- Fallback mode (Spec note): for use with the stock N7DDC firmware, `button_emulation.py` drives three outputs wired across the Tune, A/M and Bypass buttons via optocouplers, using press durations taken from the original firmware. Select serial vs fallback mode in `remote/config.py`. Document what is lost in fallback mode (status data, power interlock, direct L/C control).
- If the ukoda firmware proves unworkable, document why in `SUMMARY.md` and leave the fallback mode as the working path.

### Both controllers

- Superloop scheduler as the Spec describes: round-robin tasks; ISRs only set flags or buffer data; an interrupt-service task runs several times per loop. Every task short and non-blocking. Use the hardware watchdog.
- State tables: current and previous, covering all I/O and data points. All changes go through one commit function that saves previous first. On error, roll back and reapply the previous state to hardware.
- Display (SSD1306, I2C 0x3C): write line 1 to 4, write char at line/position, scrollback buffer, highlighted menu item. The main screen mimics the ATU-100 exactly (e.g. "100.0W", "1.15", "1.25uH", "150pF", trailing "." for Auto, "_" for Bypass, and the post-tune efficiency screen).
- Menu: up/down/left/right/select, an "Exit Menu" item, selecting a leaf exits the menu and runs its handler. Menu defined as an easily edited data structure.
- Buttons and LEDs on the MCP23017 (0x20) using INTA/INTB with debounce, per client decisions 5 and 6.
- Errors: codes for every type listed in the Spec plus any you need, each carrying source unit and nature. Propagate ATU to Remote to Master. Local errors on the local display; system errors prominent on the Master.
- The Remote's local UI allows antenna select and ATU control when the Master link is down.

### Code quality

- MicroPython for Pico 2 W, current stable release. No dependencies beyond MicroPython built-ins; include drivers.
- Every module opens with a comment explaining its purpose and place in the system. Every function has a docstring. Non-obvious lines explain why, not just what. Write for someone who knows radio and basic Python but not embedded design patterns.
- All tunables (pins, addresses, baud rates, delays, thresholds, timeouts, button maps, LED meanings) in `config.py`, each commented.
- Consistent naming, no dead code, no allocation inside ISRs.

### Testing

- pytest suite with mocks for UART, I2C and Pin covering: frame encode/decode, CRC, corrupt frame rejection, retries, state commit/rollback, relay break-before-make and single-relay rule, interlock, ukoda JSON parsing and command mapping, Test mode emulation via relay bit sets, menu navigation, display formatting vs ATU-100.
- A simulator that runs Master and Remote logic together in CPython against a simulated ATU-100 speaking the ukoda protocol.
- `docs/TEST_PLAN.md`: step-by-step bench procedure for real hardware, starting with no RF, then low power into a dummy load, then antennas.

### Documentation (`docs/`)

- `README.md`: overview, block diagram, quick start
- `PROTOCOL.md`: RS485 frame and command set with byte-level examples
- `ATU_LINK.md`: ukoda protocol usage, command mapping, any firmware changes
- `WIRING.md`: pinout tables for both Picos, MCP23017, U094, OLED, relay drivers, ATU-100 connections, level shifting
- `FLASHING.md`: installing MicroPython, copying files with mpremote, building (MPLAB X/XC8) and flashing (PICkit) the ATU-100 firmware, backing up the original firmware first
- `ASSUMPTIONS.md`: client decisions first, then every other decision where the Spec was silent, with rationale and where to change it
- `CUSTOMIZING.md`: common tweaks (add a command, change button map, add a menu item, change delays)

There is already a root `README.md` from the loadout skeleton. The project overview README belongs at `docs/README.md` as specified. Update the root README only with a short pointer to `docs/README.md` if the plan judges that necessary so the repo is not left with a one-line stub that hides the project.

## Safety

RF at 100 W. Never energize more than one relay. Default to all relays off on any startup or unrecoverable fault. Never switch antennas while RF is detected unless explicitly overridden.

## Done when

All deliverables exist, all host tests pass, every command in the Spec tables is implemented or documented as deferred with a reason, and `SUMMARY.md` lists what was built, what could not be verified without hardware, and open questions for the client.

## Spec command tables (transcribed)

Bit-bang table names are historical. The ATU link is UART/JSON (decision 3). Implement the Master/Remote command names.

Commands that must exist: ACK, HHH, RPT, STA, RS, RR, AT0, AT1, AT2, AT3, AT4, TUN, BYP0, BYP1, AM0, AM1, TST0, TST1, TUP, TDN, TSC, TSL, SND, RCVD, ERR, RST, RST RDY, F86.

Antenna path: Master sends ATn, Remote drives the relay bank (one at a time, break-before-make), then ACK ATn.

ATU path: Master sends TUN / BYP0 / BYP1 / AM0 / AM1 / TST0 / TST1 / TUP / TDN / TSC / TSL; Remote applies them on the ATU link or button-emulation fallback and ACKs.

ERR carries an error code. SND / RCVD / RPT move a status data packet. F86 shuts down all hardware (relays off). RST resets toward a normal power-up cycle. RST RDY is the power-on ready notice. STA after RST RDY requests remote operational status.

Display formats from the Spec:

- Forward power: one decimal place plus "W" (example "100.0W").
- SWR: two decimal places, no units (example "1.15").
- L: two decimal places plus "uH" (example "1.25uH"). Inductance from the tuner may arrive in nH and must be converted.
- C: integer picofarads plus "pF" (example "150pF").
- Trailing "." on line 1 means Auto. Trailing "_" means Bypass.
- After a tune sequence, a screen can show forward power, SWR, power at the antenna, and efficiency percent. Confirm the exact trigger from the N7DDC v3.2 source.

Error types named by the Spec: Failed to Execute Command, Data Not Available, Resource offline, Communication Lost with unit, Data Corrupted. Add any others the implementation needs. Each error carries source unit and nature.

## Host constraints

- Tests run on the PC with pytest. MicroPython hardware modules (`machine`, `uasyncio` if used) must be imported only behind a boundary the tests can mock. Prefer a design that imports cleanly under CPython.
- No third-party runtime dependencies. pytest may be used on the host only.
- Do not require network, hardware, or a PIC compiler for the host test suite to pass.
