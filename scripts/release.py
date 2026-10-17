"""Release chores, so a new version can't ship without its notes or its upgrade test.

    uv run python scripts/release.py prepare 0.3.0    # check the notes, bump the version, add the fixture home
    uv run python scripts/release.py notes v0.3.0     # the CHANGELOG section (the release workflow's body)
    uv run python scripts/release.py fixture NAME [--legacy]

`prepare` refuses until CHANGELOG.md and the guide's "Nyheder" chapter both have a `## 0.3.0` section. It then
sets the version in pyproject.toml and web/package.json and writes tests/fixtures/homes/v0.3.0/: a small data
folder made by this version, with synthetic data. tests/test_upgrade.py opens every fixture home with the current
code, so a later version that can't read what an earlier one wrote fails its tests instead of a user's data.
Then: run the tests, publish (scripts/publish_public.py), tag v0.3.0 in the public repo.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
NEWS = ROOT / "guide" / "brugervejledning" / "nyheder.md"
FIXTURES = ROOT / "tests" / "fixtures" / "homes"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def section(text: str, version: str) -> str | None:
    """The `## <version>` section of a Markdown file (up to the next `## `), without its heading."""
    m = re.search(rf"^## v?{re.escape(version)}\b.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else None


def notes(version: str) -> str:
    v = version.lstrip("v")
    s = section(CHANGELOG.read_text(encoding="utf-8"), v)
    if s is None:
        sys.exit(f"CHANGELOG.md has no '## {v}' section")
    return s


def _set_version(path: Path, pattern: str, version: str) -> None:
    text = path.read_bytes().decode("utf-8")
    new, n = re.subn(pattern, lambda m: m.group(1) + version + m.group(2), text, count=1, flags=re.M)
    if n != 1:
        sys.exit(f"no version found in {path}")
    path.write_bytes(new.encode("utf-8"))


def prepare(version: str) -> None:
    if not VERSION.match(version):
        sys.exit("the version is X.Y.Z, e.g. 0.3.0")
    missing = [p.name for p in (CHANGELOG, NEWS) if section(p.read_text(encoding="utf-8"), version) is None]
    if missing:
        sys.exit(f"write the '## {version}' section first in: {', '.join(missing)}")
    _set_version(ROOT / "pyproject.toml", r'^(version = ")[^"]+(")', version)
    _set_version(ROOT / "web" / "package.json", r'^(  "version": ")[^"]+(")', version)
    target = FIXTURES / f"v{version}"
    if not target.exists():
        print("The fixture home is made by the code as it is now: run `uv sync` so the new version number is in "
              "place, then: uv run python scripts/release.py fixture v" + version)
    print(f"Version {version} set. Next: uv sync, the fixture (if new), uv run pytest -q, pnpm -C web test, "
          "then scripts/publish_public.py and the tag.")


# ---------------- fixture data folders ----------------

def fixture(name: str, legacy: bool = False) -> Path:
    """A small data folder with synthetic data, made by the current code, for tests/test_upgrade.py."""
    sys.path.insert(0, str(ROOT / "src"))
    import pandas as pd

    from radar import home, manifest, paths, userstore

    target = FIXTURES / name
    if target.exists():
        sys.exit(f"{target} exists; a fixture is never changed once released")
    with tempfile.TemporaryDirectory() as t:
        build = Path(t) / name
        if legacy:                                 # the layout before the data folder: inside the install folder
            (build / "src" / "radar").mkdir(parents=True)
            (build / "pyproject.toml").write_text('[project]\nname = "market-radar"\n', encoding="utf-8")
            loc = paths.Locations.legacy(build)
            paths.configure(loc)
        else:
            loc = home.create(build, Path(t) / "cache", pointer=False)
        pid = userstore.save_portfolio({"name": "Testdepot", "mode": "real", "kind": "frie_midler", "tags": ["lang"]})
        for sym, d, typ, q, px in (("NOVO-B.CO", "2025-03-03", "BUY", 10, 650.0), ("MSFT", "2025-04-01", "BUY", 2, 380.0),
                                   ("NOVO-B.CO", "2025-09-01", "SELL", 4, 420.0)):
            userstore.add_tx({"portfolio_id": pid, "symbol": sym, "date": d, "type": typ, "quantity": q, "price": px})
        userstore.add_tx({"portfolio_id": pid, "symbol": None, "date": "2025-03-01", "type": "DEPOSIT",
                          "amount": 20000.0, "currency": "DKK"})
        userstore.watch("ASML.AS")
        userstore.meta_set("regime_votes", {"valuation": False})
        for rel, text in (("notes/investor.md", "# Investor\nHorisont: 10 år. Æøå."),
                          ("research/MSFT.md", "# MSFT\nTese."),
                          ("journal/2025-04-01-MSFT-buy.md", "---\nstatus: open\n---\n# Køb MSFT\n")):
            f = loc.home / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
        snaps = loc.history / "snapshots"
        snaps.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"ticker": ["A", "B"], "rank": [1, 2], "score": [0.9, 0.1], "region": "us"}).to_parquet(
            snaps / "2025-09-01_momentum.parquet", index=False)
        expected = {"layout": "legacy" if legacy else "home", "made_by": manifest.app_version(),
                    "home_format": None if legacy else home.HOME_FORMAT, "tables": home.table_counts(loc.userdata / home.DB_NAME),
                    "files": sorted(p.relative_to(build).as_posix() for p in build.rglob("*") if p.is_file()
                                    and p.suffix != ".db" and p.name != manifest.MANIFEST)}
        (build / "expected.json").write_text(json.dumps(expected, indent=1, ensure_ascii=False), encoding="utf-8")
        paths.configure(None)
        shutil.copytree(build, target)
    print(f"Wrote {target}")
    return target


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare").add_argument("version")
    sub.add_parser("notes").add_argument("version")
    f = sub.add_parser("fixture")
    f.add_argument("name")
    f.add_argument("--legacy", action="store_true", help="the layout from before the data folder")
    a = ap.parse_args()
    if a.cmd == "prepare":
        prepare(a.version)
    elif a.cmd == "notes":
        print(notes(a.version))
    else:
        fixture(a.name, a.legacy)


if __name__ == "__main__":
    main()
