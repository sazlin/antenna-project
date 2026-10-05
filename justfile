source_ref := `grep '^ref:' .loadout.yaml | awk '{print $2}'`
source_url := `grep '^source:' .loadout.yaml | awk '{print $2}'`
loadout := "uvx --from git+" + source_url + "@" + source_ref + " loadout"

# Apply the pinned rules and skills to this repo
loadout-sync:
    {{loadout}} sync

# Fail if .cursor/ does not match the lockfile
loadout-check:
    {{loadout}} sync --check

# Bump to the latest release and re-sync
loadout-update:
    {{loadout}} update

# List what the current manifest resolves to
loadout-list:
    {{loadout}} resolve --list
