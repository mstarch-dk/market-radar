"""Is a newer Market Radar out? Off until you switch it on (the Data page, or `radar updates --on`); then at most
one request a day to GitHub's releases API for the public repo (settings.yaml `updates.repo`), through net.py like
every other request. Nothing about you is sent. The answer is kept in the cache folder.

Updating stays a manual step: download the new zip, unzip it anywhere, start it. It finds your data folder.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from . import home, paths
from .config import settings

CHECK_FILE = paths.CACHE / "updates.json"
EVERY = timedelta(days=1)


def repo() -> str | None:
    return (settings().get("updates") or {}).get("repo") or None


def enabled() -> bool:
    m = home.read_manifest(paths.locations().home) or {}
    return bool(m.get("update_check"))


def set_enabled(on: bool) -> None:
    loc = paths.locations()
    m = home.read_manifest(loc.home)
    if m is None:
        raise RuntimeError("the update check needs a data folder: run `radar setup` first")
    m["update_check"] = bool(on)
    home._write_manifest(loc.home, home._log(m, "update_check", on=bool(on)))


def _cached() -> dict | None:
    try:
        return json.loads(CHECK_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None


def status(check: bool = True) -> dict:
    """{enabled, repo, current, latest, newer, url, published, checked, error}; checks GitHub when due."""
    out = {"enabled": False, "repo": repo(), "current": home.app_version(), "latest": None, "newer": False,
           "url": None, "published": None, "checked": None, "error": None}
    try:
        out["enabled"] = enabled()
    except paths.NotSetUp:
        return out
    if not out["enabled"] or not out["repo"]:
        return out
    c = _cached()
    due = not c or c.get("repo") != out["repo"] or datetime.fromisoformat(c["checked"]) < datetime.now() - EVERY
    if check and due:
        c = _fetch(out["repo"])
        CHECK_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHECK_FILE.write_text(json.dumps(c, indent=1), encoding="utf-8")
    if c:
        out |= {k: c.get(k) for k in ("latest", "url", "published", "checked", "error")}
        out["newer"] = bool(out["latest"]) and home._vt(out["latest"].lstrip("v")) > home._vt(out["current"])
    return out


def _fetch(repo_name: str) -> dict:
    from . import net

    now = datetime.now().isoformat(timespec="seconds")
    try:
        r = net.get(f"https://api.github.com/repos/{repo_name}/releases/latest", source="updates", timeout=10,
                    expected=(404,), headers={"Accept": "application/vnd.github+json"})
        if r.status_code == 404:
            return {"repo": repo_name, "checked": now, "error": "no release published yet"}
        d = r.json()
        return {"repo": repo_name, "checked": now, "latest": d.get("tag_name"), "url": d.get("html_url"),
                "published": (d.get("published_at") or "")[:10] or None, "error": None}
    except Exception as e:                        # offline is normal: say so, try again tomorrow
        return {"repo": repo_name, "checked": now, "error": f"{type(e).__name__}: {e}"[:200]}
