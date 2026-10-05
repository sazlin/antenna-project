# Flashing

## Pico 2 W

Hold BOOTSEL and copy the MicroPython v1.29.0 UF2 for `RPI_PICO2_W` (2026-08-24).

Then copy the tree with mpremote. The board boots `/main.py`, so the board's `main.py` is copied to that name. Imports stay `master.config` and `remote.config`.

Master:

```bash
mpremote cp -r common :
mpremote cp -r master :
mpremote cp master/main.py :main.py
```

Remote:

```bash
mpremote cp -r common :
mpremote cp -r remote :
mpremote cp remote/main.py :main.py
```

## ATU-100

Back up the original PIC hex before writing. Read the chip into a backup file first:

```bash
pk2cmd -PPIC16F1938 -GF backup-original.hex
```

The image to write is the pinned ukoda tree plus the `Forward` diff in `atu100_firmware/README.md`, built with MPLAB X and XC8 or the ukoda docker flow. This host cannot run XC8, so the bench image is not produced here. The untouched upstream hex does not add the `Forward` field.
