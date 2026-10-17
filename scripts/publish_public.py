"""Export a clean copy of this repo for the public repo: no personal files, a leak check, a neutral author.

This repo stays private (its history holds personal briefs). The public repo gets one fresh commit per
release, built from the current HEAD:

    uv run python scripts/publish_public.py --out ../market-radar-public-export        # dry run: export + check
    uv run python scripts/publish_public.py --repo ../market-radar-public --version v0.1 [--zip]

Steps:
1. `git archive HEAD` into a temporary folder (only committed files, nothing local).
2. Remove the paths in publish/exclude.txt (briefs, journal, research, ...).
3. Add publish/overlay/ (the public repo's own workflows: release zip, smoke tests).
4. Leak check: refuse to continue if any file contains a pattern from notes/leak-patterns.txt (local) or the
   git author's name and email.
5. --out: write the clean tree there.
   --repo: replace the public clone's files and commit as "Market Radar". Pushing and tagging stay a manual
   step; the commands are printed.
   --zip: also build the release zip (needs web/dist).
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = ROOT / "publish" / "exclude.txt"
OVERLAY = ROOT / "publish" / "overlay"
PATTERNS = ROOT / "notes" / "leak-patterns.txt"
AUTHOR = {"GIT_AUTHOR_NAME": "Market Radar", "GIT_AUTHOR_EMAIL": "market-radar@users.noreply.github.com",
          "GIT_COMMITTER_NAME": "Market Radar", "GIT_COMMITTER_EMAIL": "market-radar@users.noreply.github.com"}
TEXT_SUFFIXES = {".py", ".md", ".ts", ".tsx", ".css", ".json", ".yaml", ".yml", ".toml", ".txt", ".csv", ".html",
                 ".cmd", ".command", ".sh", ".lock", ".cfg", ".ini", ".gitignore", ".gitattributes", ""}


def git(*args: str, cwd: Path = ROOT, env: dict | None = None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env={**os.environ, **(env or {})}).stdout.strip()


def export_head(dest: Path) -> None:
    data = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        t.extractall(dest, filter="data")


def apply_excludes(tree: Path) -> list[str]:
    removed = []
    for line in EXCLUDE.read_text(encoding="utf-8").splitlines():
        pat = line.split("#", 1)[0].strip()
        if not pat:
            continue
        for p in sorted(tree.glob(pat.rstrip("/"))):
            removed.append(p.relative_to(tree).as_posix())
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    return removed


def leak_patterns() -> list[str]:
    pats = []
    if PATTERNS.exists():
        pats += [x.strip() for x in PATTERNS.read_text(encoding="utf-8").splitlines()
                 if x.strip() and not x.lstrip().startswith("#")]
    for key in ("user.name", "user.email"):
        try:
            v = git("config", key)
        except subprocess.CalledProcessError:
            v = ""
        if v:
            pats.append(v)
    return pats


def leak_check(tree: Path, patterns: list[str]) -> list[str]:
    """Every occurrence of a personal pattern in a text file, as 'path:line: text'."""
    if not patterns:
        sys.exit("No leak patterns: create notes/leak-patterns.txt (your name, email, account and holding names).")
    rx = re.compile("|".join(re.escape(p) for p in patterns), re.IGNORECASE)
    hits = []
    for f in sorted(tree.rglob("*")):
        if not f.is_file() or (f.suffix.lower() not in TEXT_SUFFIXES and f.name not in (".gitignore", ".gitattributes")):
            continue
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(lines, 1):
            if rx.search(line):
                hits.append(f"{f.relative_to(tree).as_posix()}:{i}: {line.strip()[:120]}")
    return hits


def sync_into(tree: Path, repo: Path) -> None:
    """Make the public clone's working tree equal to `tree` (its .git untouched)."""
    for p in repo.iterdir():
        if p.name != ".git":
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    shutil.copytree(tree, repo, dirs_exist_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Export a clean public copy of this repo.")
    ap.add_argument("--out", type=Path, help="write the clean tree here (dry run)")
    ap.add_argument("--repo", type=Path, help="a local clone of the public repo to commit into")
    ap.add_argument("--version", default="", help="release name for the commit message, e.g. v0.1")
    ap.add_argument("--zip", action="store_true", help="also build the release zip (needs web/dist)")
    a = ap.parse_args()
    if not a.out and not a.repo:
        ap.error("give --out (dry run) and/or --repo")
    if git("status", "--porcelain", "--untracked-files=no"):
        print("Note: uncommitted changes are not exported; only HEAD is.")

    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "market-radar"
        tree.mkdir()
        export_head(tree)
        removed = apply_excludes(tree)
        if OVERLAY.exists():
            shutil.copytree(OVERLAY, tree, dirs_exist_ok=True)
        print(f"Exported HEAD {git('rev-parse', '--short', 'HEAD')}; left out: {', '.join(removed) or 'nothing'}")

        hits = leak_check(tree, leak_patterns())
        if hits:
            print("LEAK CHECK FAILED. Personal strings found; nothing was written:")
            print("\n".join(f"  {h}" for h in hits))
            sys.exit(1)
        print("Leak check passed.")

        if a.out:
            if a.out.exists():
                shutil.rmtree(a.out)
            shutil.copytree(tree, a.out)
            print(f"Clean tree written to {a.out}")
        if a.zip:
            sys.path.insert(0, str(ROOT / "scripts"))
            from build_release_zip import build

            dist_src = ROOT / "web" / "dist"
            shutil.copytree(dist_src, tree / "web" / "dist", dirs_exist_ok=True) if dist_src.exists() else None
            name = f"market-radar-{a.version or 'snapshot'}"
            path = build(tree, ROOT / "dist-release" / f"{name}.zip", name)
            print(f"Release zip: {path}")
        if a.repo:
            if not (a.repo / ".git").exists():
                sys.exit(f"{a.repo} is not a git clone (clone the public repo there first).")
            sync_into(tree, a.repo)
            git("add", "-A", cwd=a.repo)
            if not git("status", "--porcelain", cwd=a.repo):
                print("The public repo already matches; nothing to commit.")
                return
            msg = f"Release {a.version}".strip() if a.version else "Update"
            git("commit", "-m", msg, cwd=a.repo, env=AUTHOR)
            print(f"Committed to {a.repo} as \"Market Radar\". Review it, then publish with:")
            print(f"  git -C {a.repo} push")
            if a.version:
                print(f"  git -C {a.repo} tag {a.version} && git -C {a.repo} push origin {a.version}"
                      "   # builds the release zip on GitHub")


if __name__ == "__main__":
    main()
