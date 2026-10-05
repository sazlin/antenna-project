import ast
from pathlib import Path


def test_modules_and_functions_are_explained():
    missing = []
    for root in ("common", "master", "remote"):
        for path in Path(root).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            lines = [line for line in text.splitlines() if line.strip()]
            if not lines or not lines[0].startswith("#"):
                missing.append(f"{path.as_posix()} module")
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    if not ast.get_docstring(node):
                        missing.append(f"{path.as_posix()}:{node.name}")
    assert missing == []
    assert "AM0 turns Auto on and AM1 turns Auto off." in Path("remote/atu_link.py").read_text(encoding="utf-8")
    assert "only place a coil is turned on" in Path("remote/relays.py").read_text(encoding="utf-8")
