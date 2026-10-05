import sys
from pathlib import Path

import master.main
import master.tasks
import remote.atu_link
import remote.main
import remote.relays
import remote.tasks


def test_machine_import_stays_inside_hal():
    assert master.main and remote.main
    assert "machine" not in sys.modules
    offenders = []
    for root in ("common", "master", "remote"):
        for path in Path(root).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "import machine" in text:
                offenders.append(path.as_posix())
            if root == "master" and "import remote" in text:
                offenders.append(path.as_posix() + ":remote")
            if root == "remote" and "import master" in text:
                offenders.append(path.as_posix() + ":master")
    assert offenders == ["common/hal.py"]
