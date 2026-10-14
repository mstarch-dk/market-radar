"""Build the download for non-technical users: the tracked files plus the prebuilt web app (web/dist), so nobody
needs Node. The macOS start script keeps its executable bit.

    uv run python scripts/build_release_zip.py [--root DIR] [--out market-radar-vX.zip] [--prefix market-radar]

Run `pnpm -C web build` first (the release workflow does). Used by .github/workflows/release.yml and by
scripts/publish_public.py --zip.
"""
from __future__ import annotations

import argparse
import stat
import subprocess
import sys
import zipfile
from pathlib import Path


def tracked_files(root: Path) -> list[Path]:
    """Files git tracks in `root`; without git (an exported tree), every file except .git."""
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
        return [root / p for p in out.decode().split("\0") if p]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [p for p in root.rglob("*") if p.is_file() and ".git" not in p.relative_to(root).parts]


def build(root: Path, out: Path, prefix: str) -> Path:
    dist = root / "web" / "dist"
    if not (dist / "index.html").exists():
        sys.exit("web/dist is missing: run `pnpm -C web install && pnpm -C web build` first.")
    files = sorted(set(tracked_files(root)) | {p for p in dist.rglob("*") if p.is_file()})
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            if not f.exists():
                continue
            rel = f.relative_to(root).as_posix()
            info = zipfile.ZipInfo.from_file(f, f"{prefix}/{rel}")
            mode = 0o755 if f.suffix in (".command", ".sh") else 0o644    # the Mac script must be executable
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, f.read_bytes())
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--out", type=Path, default=Path("dist-release/market-radar.zip"))
    ap.add_argument("--prefix", default="market-radar")
    a = ap.parse_args()
    path = build(a.root.resolve(), a.out, a.prefix)
    print(f"Wrote {path} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
