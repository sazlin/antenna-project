# Customizing

Add a command in `common/commands.py`. Give it a free byte and a mnemonic, then handle that mnemonic where the remote dispatches frames.

Change a button in `master/config.py`. The name list and the bit map are the two places a front-panel key is defined.

Add a menu item in `common/menu.py`. Put a leaf on Antenna or Tuner with a handler name that already exists, or add the handler in the same change.

Change `RELAY_DELAY_MS` in `remote/config.py` when a coil is slow to release. 100 ms is the starting value.
