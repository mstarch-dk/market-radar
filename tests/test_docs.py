"""The developer docs stay short-lined and name only modules that exist (docs/*.md; the guide has test_guide.py)."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "radar"
DOCS = sorted((ROOT / "docs").glob("*.md"))
MAX = 200


def prose(path: Path):
    """(line number, line) outside code blocks and tables."""
    fence = False
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("```"):
            fence = not fence
            continue
        if not fence and not line.lstrip().startswith("|"):
            yield n, line


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_no_long_lines_outside_tables_and_code(doc):
    long = [f"{doc.name}:{n} ({len(line)})" for n, line in prose(doc) if len(line) > MAX]
    assert not long, f"lines over {MAX} characters: wrap them: {long}"


def test_every_module_path_in_the_architecture_exists():
    """A `foo/bar.py` resolves under src/radar or the repo root; a bare `foo.py` exists somewhere in src/radar."""
    modules = {p.name for p in SRC.rglob("*.py")}
    text = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    missing = []
    for name in sorted(set(re.findall(r"`([\w./]+\.py)`", text))):
        if "/" in name:
            if not ((SRC / name).exists() or (ROOT / name).exists()):
                missing.append(name)
        elif name not in modules:
            missing.append(name)
    assert not missing, f"docs/architecture.md names modules that don't exist: {missing}"
