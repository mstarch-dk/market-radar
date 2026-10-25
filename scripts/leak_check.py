"""Leak check: refuse personal strings (holdings, account names, the private email) in what git would publish.

The patterns live outside git, in notes/leak-patterns.txt (one per line, case-insensitive), plus the git
author's email unless it is a GitHub noreply address. Lines listed in notes/leak-allow.txt ('path: line') are
accepted as harmless. Both files are local, so this runs on your computer, not in CI. A linked git worktree
without its own notes/ uses the main checkout's.

    uv run python scripts/leak_check.py                    # tracked and new files in the working tree
    uv run python scripts/leak_check.py --history          # every file version and commit message ever committed
    uv run python scripts/leak_check.py --range main..HEAD # what those commits add
    uv run python scripts/leak_check.py --install-hook     # run it before every `git push` (.git/hooks/pre-push)

Exit status 1 when anything is found; the hits are printed as 'where:line: text'.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def notes_dir() -> Path:
    """This checkout's notes/, or, in a linked git worktree that has no patterns file of its own (notes/ is
    gitignored, so a new worktree never has one), the main checkout's: the patterns stay in one place."""
    own = ROOT / "notes"
    if (own / "leak-patterns.txt").exists():
        return own
    try:
        common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT,
                                check=True, capture_output=True, text=True).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return own
    main = Path(common).parent / "notes"
    return main if Path(common).name == ".git" and (main / "leak-patterns.txt").exists() else own


NOTES = notes_dir()
PATTERNS = NOTES / "leak-patterns.txt"
ALLOW = NOTES / "leak-allow.txt"  # local: 'path: line' hits known to be harmless
TEXT_SUFFIXES = {".py", ".md", ".ts", ".tsx", ".css", ".json", ".yaml", ".yml", ".toml", ".txt", ".csv", ".html",
                 ".cmd", ".command", ".sh", ".ps1", ".lock", ".cfg", ".ini", ".j2", ".mjs", ".gitignore",
                 ".gitattributes", ""}
ZERO = "0" * 40


def git(*args: str, input: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, input=input).stdout


def leak_patterns() -> list[str]:
    pats = []
    if PATTERNS.exists():
        pats += [x.strip() for x in PATTERNS.read_text(encoding="utf-8").splitlines()
                 if x.strip() and not x.lstrip().startswith("#")]
    try:
        email = git("config", "user.email").decode().strip()
    except subprocess.CalledProcessError:
        email = ""
    if email and not email.endswith("@users.noreply.github.com"):
        pats.append(email)
    return pats


def leak_allowed() -> set[str]:
    """Hits accepted as harmless, one 'path: stripped line' per line (no line number, so edits elsewhere in the
    file keep them; any change to the line itself makes it a hit again)."""
    if not ALLOW.exists():
        return set()
    return {x.strip() for x in ALLOW.read_text(encoding="utf-8").splitlines()
            if x.strip() and not x.lstrip().startswith("#")}


def _regex(patterns: list[str]) -> re.Pattern[str]:
    if not patterns:
        sys.exit("No leak patterns: create notes/leak-patterns.txt (account and holding names, anything private).")
    return re.compile("|".join(re.escape(p) for p in patterns), re.IGNORECASE)


def is_text(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name.lstrip(".") else ""
    return suffix in TEXT_SUFFIXES or name in (".gitignore", ".gitattributes")


def scan(items: Iterable[tuple[str, str]], patterns: list[str], allowed: set[str] = frozenset()) -> list[str]:
    """Every pattern hit in (where, text) pairs, as 'where:line: text', except the allowed lines. `where` is a
    path, or 'path@blob' for a file version from history: an allowed line stays allowed in every version."""
    rx = _regex(patterns)
    hits = []
    for where, text in items:
        path = where.split("@", 1)[0]
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line) and f"{path}: {line.strip()}" not in allowed:
                hits.append(f"{where}:{i}: {line.strip()[:120]}")
    return hits


def leak_check(tree: Path, patterns: list[str], allowed: set[str] = frozenset()) -> list[str]:
    """Every pattern hit in the text files under a folder."""
    def files() -> Iterator[tuple[str, str]]:
        for f in sorted(tree.rglob("*")):
            rel = f.relative_to(tree).as_posix()
            if f.is_file() and is_text(rel):
                try:
                    yield rel, f.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
    return scan(files(), patterns, allowed)


def worktree_files() -> Iterator[tuple[str, str]]:
    """Tracked and new files, never ignored ones: what the next commit could hold."""
    out = git("ls-files", "-z", "--cached", "--others", "--exclude-standard").decode("utf-8")
    for rel in filter(None, out.split("\0")):
        f = ROOT / rel
        if f.is_file() and is_text(rel):
            try:
                yield rel, f.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue


def blobs(revs: list[str]) -> Iterator[tuple[str, str]]:
    """Each distinct text file version reachable from `revs` (as `git rev-list --objects` takes them)."""
    seen: dict[str, str] = {}
    for line in git("rev-list", "--objects", *revs).decode("utf-8").splitlines():
        sha, _, path = line.partition(" ")
        if path and sha not in seen and is_text(path):
            seen[sha] = path
    if not seen:
        return
    types = git("cat-file", "--batch-check=%(objectname) %(objecttype)",
                input="\n".join(seen).encode()).decode().splitlines()
    shas = [s for s, t in (x.split() for x in types) if t == "blob"]
    out = git("cat-file", "--batch", input="\n".join(shas).encode())
    pos = 0
    for _ in shas:
        header_end = out.index(b"\n", pos)
        sha, _, size = out[pos:header_end].decode().split()
        body = out[header_end + 1: header_end + 1 + int(size)]
        pos = header_end + 1 + int(size) + 1
        try:
            yield f"{seen[sha]}@{sha[:7]}", body.decode("utf-8")
        except UnicodeDecodeError:
            continue


def commits(revs: list[str]) -> Iterator[tuple[str, str]]:
    """Each commit's author, committer and message."""
    out = git("log", "--format=%H%x00%an <%ae>%n%cn <%ce>%n%B%x00", *revs).decode("utf-8")
    parts = out.split("\0")
    for sha, body in zip(parts[0::2], parts[1::2]):
        yield f"commit {sha.strip()[:7]}", body


def check_revs(revs: list[str], patterns: list[str], allowed: set[str]) -> list[str]:
    return scan(blobs(revs), patterns, allowed) + scan(commits(revs), patterns)


def pre_push(stdin: str) -> list[str]:
    """The commits a push would send (git passes '<local ref> <local sha> <remote ref> <remote sha>' lines): for
    a new branch, everything no remote has yet."""
    hits = []
    for line in stdin.splitlines():
        parts = line.split()
        if len(parts) != 4 or parts[1] == ZERO:  # a deleted ref sends nothing
            continue
        local, remote = parts[1], parts[3]
        revs = [local, f"^{remote}"] if remote != ZERO else [local, "--not", "--remotes"]
        hits += check_revs(revs, leak_patterns(), leak_allowed())
    return hits


HOOK = """#!/bin/sh
# Installed by scripts/leak_check.py --install-hook: refuse a push that carries personal strings.
exec uv run --no-project python scripts/leak_check.py --pre-push
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Refuse personal strings in what git would publish.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--history", action="store_true", help="every file version and commit message ever committed")
    g.add_argument("--range", metavar="A..B", help="the file versions and messages these commits add")
    g.add_argument("--pre-push", action="store_true", help="as a pre-push hook (reads the refs from stdin)")
    g.add_argument("--install-hook", action="store_true", help="install the pre-push hook in this clone")
    a = ap.parse_args()
    if a.install_hook:
        hook = Path(git("rev-parse", "--git-path", "hooks").decode().strip())
        hook = (hook if hook.is_absolute() else ROOT / hook) / "pre-push"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_bytes(HOOK.encode())
        hook.chmod(0o755)
        print(f"Installed {hook}")
        return
    patterns, allowed = leak_patterns(), leak_allowed()
    if a.pre_push:
        hits, what = pre_push(sys.stdin.read()), "the commits being pushed"
    elif a.history:
        hits, what = check_revs(["--all"], patterns, allowed), "the whole history"
    elif a.range:
        base, _, tip = a.range.partition("..")
        hits, what = check_revs([tip or "HEAD", f"^{base}"], patterns, allowed), a.range
    else:
        hits, what = scan(worktree_files(), patterns, allowed), "the working tree"
    if hits:
        print(f"LEAK CHECK FAILED in {what}. Personal strings found:")
        print("\n".join(f"  {h}" for h in hits))
        sys.exit(1)
    print(f"Leak check passed: {what}.")


if __name__ == "__main__":
    main()
