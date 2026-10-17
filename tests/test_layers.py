"""The package's shape, checked from the source. The layers are import-linter contracts in pyproject.toml (the
same as `uv run lint-imports`; see docs/architecture.md, *Layers*): the kernel imports neither the studies nor
the app, the studies don't import the report builder, the app never imports a study, and every module sits in a
layer that only imports downwards. The two checks import-linter doesn't make live here: no module reaching into
another's private names (the tests included), and no import cycles. Function-local imports count everywhere:
they hide a dependency from the reader, not from the program.

Run this file directly (`uv run python tests/test_layers.py`) to print the current findings."""
from __future__ import annotations

import ast
import re
from collections import defaultdict
from functools import cache
from pathlib import Path

from importlinter.cli import lint_imports

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"

# Test files allowed to read a module's private name: (test file, module, name). It only shrinks; empty since
# Tranche 10 (a test that needs a stand-in or a helper of its own uses a public seam, docs/testing.md).
TEST_PRIVATE_ALLOWED: frozenset[tuple[str, str, str]] = frozenset()

@cache
def _modules() -> dict[str, Path]:
    out = {}
    for p in (SRC / "radar").rglob("*.py"):
        parts = p.relative_to(SRC).with_suffix("").parts
        out[".".join(parts[:-1] if parts[-1] == "__init__" else parts)] = p
    return out


def _base(cur: str, node: ast.ImportFrom) -> str:
    """The module an ImportFrom reads from, absolute."""
    if not node.level:
        return node.module or ""
    pkg = cur.split(".") if _modules()[cur].name == "__init__.py" else cur.split(".")[:-1]
    pkg = pkg[: len(pkg) - (node.level - 1)]
    return ".".join(pkg + ([node.module] if node.module else []))


def _owner(name: str) -> str | None:
    """The radar module `name` is, or lives in."""
    mods = _modules()
    while name and name not in mods:
        name = name.rpartition(".")[0]
    return name or None


@cache
def _scan() -> tuple[dict[str, set[str]], set[tuple[str, str, str]]]:
    """Every module's radar imports (top-level and function-local) and the private names it reads elsewhere."""
    deps: dict[str, set[str]] = defaultdict(set)
    private: set[tuple[str, str, str]] = set()
    for cur, path in _modules().items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases: dict[str, str] = {}                    # a local name bound to a radar module
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                base = _base(cur, node)
                for a in node.names:
                    full = f"{base}.{a.name}"
                    if full in _modules():               # `from . import x`: a module
                        deps[cur].add(full)
                        aliases[a.asname or a.name] = full
                    elif (owner := _owner(base)) is not None:
                        deps[cur].add(owner)
                        if a.name.startswith("_") and owner != cur:
                            private.add((cur, owner, a.name))
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if (owner := _owner(a.name)) is not None:
                        deps[cur].add(owner)
                        if a.asname:
                            aliases[a.asname] = owner
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in aliases
                    and node.attr.startswith("_") and not node.attr.startswith("__")
                    and aliases[node.value.id] != cur):
                private.add((cur, aliases[node.value.id], node.attr))
        deps[cur].discard(cur)
    return dict(deps), private


def _private(name: str) -> bool:
    return name.startswith("_") and not name.startswith("__")


@cache
def _scan_tests() -> set[tuple[str, str, str]]:
    """The private names of radar modules the test files read: imported, as attributes of a module, patched by
    name (`monkeypatch.setattr(mod, "_x", …)`) or by dotted string ("radar.mod._x")."""
    mods = _modules()
    found: set[tuple[str, str, str]] = set()
    for path in sorted(TESTS.rglob("*.py")):
        test = path.relative_to(TESTS).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (owner := _owner(node.module or "")) is not None:
                for a in node.names:
                    if f"{node.module}.{a.name}" in mods:
                        aliases[a.asname or a.name] = f"{node.module}.{a.name}"
                    elif _private(a.name):
                        found.add((test, owner, a.name))
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in mods and a.asname:
                        aliases[a.asname] = a.name
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in aliases
                    and _private(node.attr)):
                found.add((test, aliases[node.value.id], node.attr))
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr in ("setattr", "delattr") and len(node.args) >= 2
                  and isinstance(node.args[0], ast.Name) and node.args[0].id in aliases
                  and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str)
                  and _private(node.args[1].value)):
                found.add((test, aliases[node.args[0].id], node.args[1].value))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and (
                    m := re.fullmatch(r"(radar(?:\.\w+)*)\.(_\w+)", node.value)) and _private(m[2]):
                found.add((test, _owner(m[1]) or m[1], m[2]))
    return found


def _cycles() -> list[list[str]]:
    """The strongly connected components with more than one module (Tarjan)."""
    deps, _ = _scan()
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on: set[str] = set()
    out: list[list[str]] = []

    def visit(v: str) -> None:
        index[v] = low[v] = len(index)
        stack.append(v)
        on.add(v)
        for w in deps.get(v, ()):
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                out.append(sorted(comp))

    for m in sorted(_modules()):
        if m not in index:
            visit(m)
    return out


def test_the_import_contracts_hold(capsys):
    """A broken contract names the chain of imports: move the shared piece down a layer, or pass it in from above,
    rather than adding an exception (ignore_imports is empty)."""
    code = lint_imports(config_filename=str(ROOT / "pyproject.toml"), no_cache=True, no_logo=True)
    assert code == 0, capsys.readouterr().out


def test_no_module_uses_another_modules_private_names():
    """A name with a leading underscore is free to change with its module. One that another module needs is part
    of the API: make it public there, or move it where it belongs."""
    found = sorted(_scan()[1])
    assert not found, "uses of another module's private names:\n" + "\n".join(f"  {x}" for x in found)


def test_no_test_reads_a_private_name():
    """A test that reaches into a module's internals breaks when they are refactored, though the behaviour holds.
    Test through the public function, or make a real seam public (a config reader or a download a test replaces:
    `external.cfg`, `factors.fetch`); the allowlist only shrinks."""
    found = _scan_tests()
    new = sorted(found - TEST_PRIVATE_ALLOWED)
    assert not new, "tests reading a private name:\n" + "\n".join(f"  {x}" for x in new)
    gone = sorted(TEST_PRIVATE_ALLOWED - found)
    assert not gone, "no longer used, take them off TEST_PRIVATE_ALLOWED:\n" + "\n".join(f"  {x}" for x in gone)


def test_no_import_cycles():
    """Modules in one cycle can only be understood, tested and changed together. A dependency points down a
    layer; when two modules need each other, the shared piece belongs below both."""
    assert not _cycles(), "import cycles:\n" + "\n".join(f"  {', '.join(c)}" for c in _cycles())


if __name__ == "__main__":
    for a, b, n in sorted(_scan()[1]):
        print(f"{a} uses {b}.{n}")
    for t, b, n in sorted(_scan_tests()):
        print(f"tests/{t} uses {b}.{n}")
    for c in _cycles():
        print(f"cycle of {len(c)}: {', '.join(c)}")
