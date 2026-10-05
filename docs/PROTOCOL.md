# RS485 protocol

The master polls. The remote does not transmit until the master polls. That keeps the U094 half-duplex link from colliding. There is no DE pin.

## Frame

Start byte `0x7E`. End byte `0x7F`. Escape byte `0x7D`. A data byte equal to start, end, or escape is sent as `0x7D` followed by the byte XOR `0x20`. CRC and length are over the unescaped body.

Body, in order: source, destination, sequence, command, length, payload. Then CRC-16/CCITT-FALSE, low byte first, then the end byte.

Source and destination: master `1`, remote `2`. Sequence is an integer 1..255 and skips 0.

## Worked AT1

Body `01 02 01 11 00` is an AT1 from master to remote, sequence 1, empty payload. CRC is `0x5147`. Full frame hex is `7e010201110047517f`. ASCII `123456789` CRC is `0x29B1`.

## Commands

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
| RST RDY | 0x34 |
| F86 | 0x35 |

`Command.RST_RDY.mnemonic` is the string `RST RDY`.

ACK payload is one byte, the command being acknowledged. ERR payload is three bytes: error code, source, failed command. Sources: master 1, remote 2, atu 3.

Hot switch ERR example: payload `06 02 11`. Code 6 is hot switch, source 2 is the remote, `0x11` is AT1.

## Status payload

SND payload is 13 bytes, little-endian multi-byte fields.

1. Flags. bit0 auto, bit1 bypass, bit2 atu link up, bit3 test mode, bit4 efficiency valid, bit5 power valid, bit6 set when Order is CL and clear when Order is LC.
2. Forward watts times 10, uint16.
3. SWR times 100, uint16.
4. Inductance nH, uint16.
5. Capacitance pF, uint16.
6. Efficiency percent, uint8.
7. Selected antenna 0..4, uint8.
8. Error code, uint8, 0 if none.
9. Error source, uint8.

Error codes: Failed to Execute 1, Data Not Available 2, Resource offline 3, Communication Lost 4, Data Corrupted 5, Hot switch 6, Relay fault 7.

## Poll, retry, and the handshake

A poll with nothing queued is HHH. The master sends a command at most 3 times, 500 ms apart, then counts one miss. Five misses show Communication Lost. The sequence does not advance until those tries are used up. Sequence 255 is followed by 1.

If the remote has a new status, it answers the idle poll with RS and an empty payload, and it does not discard the status. The master then sends RR. The remote answers SND and clears the pending status. The master then sends RCVD. The remote answers ACK. The order is RS, then RR, then SND, then RCVD.

A real command such as AT1 is executed and ACKed even while status is pending. The status handshake continues on the next idle poll. STA skips the handshake and is answered with SND directly. RPT is answered with the previous reply body and the new sequence. A duplicate sequence does not run the action again.

Log lines use mnemonics. Example: `TX AT1`, `RX ACK AT1`.
