"""Danish marketing material (marketing/) from a demo copy of the app with a fictional portfolio.

The demo runs from its own copy in .demo/: the working tree's tracked and new files (never ignored ones),
in portable mode (.demo/portable.json: its data folder is .demo/home, its market data .demo/cache), with a copy
of the market data and history and a database filled from marketing/demo/seed.yaml. Your own data folder is
never read or written, and this computer's remembered data folder is never changed.

    uv run --group marketing python scripts/marketing.py workspace   # build .demo/ (stop the demo server first)
    uv run --directory .demo radar serve --port 8790                 # the demo app (launch.json: radar-demo)
    uv run --group marketing python scripts/marketing.py seed        # fill the demo database, then `radar run`
    uv run --group marketing python scripts/marketing.py shots [ID…] # marketing/shots.yaml → marketing/site/img/
    uv run --group marketing python scripts/marketing.py pdf         # marketing/site/index.html → market-radar.pdf
    uv run --group marketing python scripts/marketing.py check       # leak check, images, features, phone width
    uv run --group marketing python scripts/marketing.py all         # all of it, starting the server itself

The /marketing skill runs these one by one and writes the text. See marketing/README.md.
"""
from __future__ import annotations

import argparse
import calendar
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leak_check as leaks  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / ".demo"
MKT = ROOT / "marketing"
SITE = MKT / "site"
IMG = SITE / "img"
PDF = MKT / "market-radar.pdf"
SEED = MKT / "demo" / "seed.yaml"
SHOTS = MKT / "shots.yaml"
FEATURES = MKT / "features.yaml"
PORT = 8790
BASE = f"http://127.0.0.1:{PORT}"
VIEWPORTS = {"desktop": {"viewport": {"width": 1440, "height": 900}, "device_scale_factor": 1.5},
             "mobile": {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2, "is_mobile": True,
                        "has_touch": True}}


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    print("$", " ".join(cmd), flush=True)
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}  # .demo/ has its own environment
    subprocess.run(cmd, cwd=cwd, check=True, env=env, shell=sys.platform == "win32" and cmd[0] == "pnpm")


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ---------------- workspace: .demo/ ----------------

def server_up(wait: float = 0) -> bool:
    """The demo server answers (waiting up to `wait` seconds for one that is starting)."""
    end = time.monotonic() + wait
    while True:
        try:
            if httpx.get(BASE + "/api/portfolios", timeout=2).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        if time.monotonic() >= end:
            return False
        time.sleep(1)


def export_worktree(dest: Path) -> None:
    """The working tree as git sees it: tracked and new files, never ignored ones (userdata/, notes/, data/, …).
    This shows work that isn't committed yet."""
    out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                         check=True, capture_output=True).stdout.decode("utf-8")
    for rel in filter(None, out.split("\0")):
        src = ROOT / rel
        if src.is_file():  # a deleted but still tracked file is skipped
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)


def workspace() -> None:
    """A fresh .demo/: the code as it is now, the market data copied in, an empty database."""
    if server_up():
        sys.exit(f"The demo server is running on port {PORT}: stop it first (its files are in use).")
    if DEMO.exists():
        shutil.rmtree(DEMO)
    DEMO.mkdir()
    export_worktree(DEMO)
    demo_home()
    run(["uv", "sync", "--directory", str(DEMO)])
    run(["pnpm", "-C", str(DEMO / "web"), "install", "--frozen-lockfile", "--prefer-offline"])
    run(["pnpm", "-C", str(DEMO / "web"), "build"])
    print(f"\n.demo/ is ready. Start it with: uv run --directory .demo radar serve --port {PORT}")


# ---------------- seed: the fictional investor ----------------

def demo_home() -> None:
    """.demo in portable mode, with an empty data folder and a copy of the market data and the history (public,
    market-derived: rank and valuation snapshots, analyst targets). Never radar.db, notes or any personal folder."""
    sys.path.insert(0, str(ROOT / "src"))
    from radar import paths
    from radar.datahome import home

    real, src = paths.resolve()
    if real is None and (ROOT / "data").is_dir():
        real = paths.Locations.legacy(ROOT)                     # this checkout hasn't moved to a data folder yet
    (DEMO / paths.PORTABLE).write_text(json.dumps({"home": "home", "cache": "cache"}), encoding="utf-8")
    demo = home.create(DEMO / "home", DEMO / "cache", pointer=False)
    paths.configure(None)
    if real is None:
        print("Note: no market data found; run `radar run` in the demo after seeding.")
        return
    for tier, dst in (("history", demo.history), ("cache", demo.cache)):
        for e in paths.REGISTRY[tier]:
            s = getattr(real, tier) / e.rstrip("/")
            if e.endswith("/") and s.is_dir():
                shutil.copytree(s, dst / e.rstrip("/"), ignore=shutil.ignore_patterns("*.tmp"), dirs_exist_ok=True)
            elif s.is_file() and e != "ops.db":
                (dst / e).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(s, dst / e)
    disc = real.reports / "discovery.json"
    if disc.exists():
        demo.reports.mkdir(parents=True, exist_ok=True)
        shutil.copy2(disc, demo.reports / "discovery.json")
    else:
        print("Note: no discovery.json; the Discover page will show its empty state.")
    for d in ("notes", "briefs", "research", "journal", "exports"):
        assert not any((demo.home / d).iterdir()), f".demo/home/{d} must be empty"
    assert not (demo.home / home.DB_NAME).exists(), "the demo database starts empty"


def months_back(today: date, spec: str) -> date:
    """'-12mo', '-3w' or '-10d' → a calendar date before `today` (the trade snaps to the close before it)."""
    m = re.fullmatch(r"-(\d+)(mo|w|d)", spec.strip())
    if not m:
        raise ValueError(f"bad relative date {spec!r} (use -12mo, -3w or -10d)")
    n, unit = int(m.group(1)), m.group(2)
    if unit == "d":
        return today - timedelta(days=n)
    if unit == "w":
        return today - timedelta(weeks=n)
    y, mo = divmod(today.year * 12 + today.month - 1 - n, 12)
    return date(y, mo + 1, min(today.day, calendar.monthrange(y, mo + 1)[1]))


class Api:
    def __init__(self) -> None:
        self.c = httpx.Client(base_url=BASE, timeout=120)

    def __call__(self, method: str, path: str, **kw):
        r = self.c.request(method, path, **kw)
        if r.status_code >= 400:
            sys.exit(f"{method} {path} → {r.status_code}: {r.text[:800]}")
        return r.json()


def _close(api: Api, symbol: str, day: date) -> dict:
    pc = api("GET", "/api/portfolio/price-check", params={"symbol": symbol, "date": day.isoformat()})
    if pc.get("close") is None or not pc.get("close_date"):
        sys.exit(f"No close for {symbol} on or before {day}: {pc.get('message')}")
    return pc


def _post_tx(api: Api, row: dict) -> None:
    res = api("POST", "/api/portfolio/transactions", json=row | {"confirm": True})
    for i in res.get("issues") or []:
        print(f"   ! {row.get('symbol') or row['type']} {row['date']}: {i.get('message', i)}")


def seed() -> None:
    if not server_up(wait=60):
        sys.exit(f"Start the demo server first: uv run --directory .demo radar serve --port {PORT}")
    spec, api = load(SEED), Api()
    today = date.today()
    existing = api("GET", "/api/portfolios")
    if any(p["n_tx"] for p in existing):
        sys.exit("The demo database already has rows: rebuild with `workspace` to seed again.")
    ids: dict[str, int] = {}
    holdings: dict[tuple[str, str], float] = {}
    for p in spec["portfolios"]:
        made = api("POST", "/api/portfolios", json={k: p[k] for k in ("name", "mode", "kind", "dividends", "note", "tags")
                                                     if k in p})
        ids[p["name"]] = made["id"]
        print(f"+ {p['name']} ({made['mode']}, {made['kind']})")
        closes = {i: _close(api, r["symbol"], months_back(today, r["at"]))
                  for i, r in enumerate(p["rows"]) if r["type"] in ("BUY", "SELL")}
        for i, r in enumerate(p["rows"]):
            day = months_back(today, r["at"])
            row = {"type": r["type"], "portfolio_id": made["id"], "note": r.get("note")}
            if r["type"] in ("BUY", "SELL"):
                pc = closes[i]
                key = (p["name"], r["symbol"])
                if r["type"] == "BUY":
                    qty = r.get("quantity") or math.floor(r["dkk"] / (pc["close"] * (pc["fx"] or 1)))
                    holdings[key] = holdings.get(key, 0) + qty
                else:
                    qty = holdings.pop(key) if r.get("quantity", "all") == "all" else r["quantity"]
                row |= {"symbol": r["symbol"], "date": pc["close_date"], "quantity": qty,
                        "price": round(pc["close"], 4), "fee": r.get("fee", 0.0)}
            else:
                # a cash row lands on the earliest close its trades of the same day snapped back to
                same = [closes[j]["close_date"] for j, t in enumerate(p["rows"]) if j in closes and t["at"] == r["at"]]
                row |= {"symbol": r.get("symbol", ""), "date": min(same, default=day.isoformat()), "amount": r["amount"]}
            _post_tx(api, row)
    for f in spec.get("forks", []):
        day = months_back(today, f["at"])
        made = api("POST", f"/api/portfolios/{ids[f['from']]}/fork",
                   json={"name": f["name"], "date": day.isoformat(), "tags": f.get("tags", []),
                         "extra_cash_dkk": f.get("extra_cash_dkk", 0.0)})
        ids[f["name"]] = made["id"]
        print(f"+ {f['name']} (fork of {f['from']} at {day})")
        for r in f.get("rows", []):
            pc = _close(api, r["symbol"], months_back(today, r["at"]))
            pos = api("GET", "/api/portfolio/positions", params={"portfolio": made["id"]})
            qty = r.get("quantity") or _held(pos, r["symbol"])
            _post_tx(api, {"type": r["type"], "symbol": r["symbol"], "date": pc["close_date"], "quantity": qty,
                           "price": round(pc["close"], 4), "fee": r.get("fee", 0.0), "portfolio_id": made["id"]})
    if spec.get("default"):
        api("POST", f"/api/portfolios/{ids[spec['default']]}/default")
    for p in api("GET", "/api/portfolios"):  # an empty starter portfolio the app may have made
        if p["name"] not in ids and not p["n_tx"]:
            api("DELETE", f"/api/portfolios/{p['id']}")
    for s in spec.get("watchlist", []):
        api("PUT", f"/api/watchlist/{s}")
    templates = {t["key"]: t for t in api("GET", "/api/views")["templates"]}
    for v in spec.get("views", []):
        t = templates[v["template"]]
        api("POST", "/api/views", json={"statement": t["statement"], "falsifier": t.get("falsifier"),
                                        "exposures": t["exposures"], "indicators": t["indicators"],
                                        "template": t["key"], "conviction": v.get("conviction", 3),
                                        "horizon": v.get("horizon", "12m"), "rationale": v.get("rationale")})
    print(f"Seeded {len(ids)} portfolios, {len(spec.get('watchlist', []))} watchlist names, "
          f"{len(spec.get('views', []))} views. Now `radar run` in .demo/ (analyst data, dashboard):")
    run(["uv", "run", "--directory", str(DEMO), "radar", "run"])
    check_demo_db()


def _held(pos: dict, symbol: str) -> float:
    for row in pos["total"]:
        if row.get("symbol") == symbol:
            return row["quantity"]
    sys.exit(f"{symbol} is not held in the fork")


def check_demo_db() -> None:
    """The demo database holds the seed's portfolios and nothing else."""
    db = DEMO / "home" / "radar.db"
    if not db.exists():
        sys.exit("No .demo/home/radar.db: run `seed`.")
    spec = load(SEED)
    want = {p["name"] for p in spec["portfolios"]} | {f["name"] for f in spec.get("forks", [])}
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as con:
        have = {r[0] for r in con.execute("SELECT name FROM portfolios")}
    if have != want:
        sys.exit(f"Demo database portfolios {sorted(have)} differ from the seed {sorted(want)}.")
    print(f"Demo database: only the seed's {len(want)} portfolios.")


# ---------------- shots: marketing/shots.yaml → site/img ----------------

def _locate(pg, loc: dict):
    el = pg.locator(loc["css"])
    if "has_text" in loc:
        el = el.filter(has_text=re.compile(loc["has_text"]))
    return el.nth(loc.get("nth", 0))


def _union(boxes: list[dict], pad: int) -> dict:
    x0 = min(b["x"] for b in boxes) - pad
    y0 = min(b["y"] for b in boxes) - pad
    x1 = max(b["x"] + b["width"] for b in boxes) + pad
    y1 = max(b["y"] + b["height"] for b in boxes) + pad
    return {"x": max(x0, 0), "y": max(y0, 0), "width": x1 - max(x0, 0), "height": y1 - max(y0, 0)}


def _act(pg, a: dict) -> None:
    if "wait" in a:
        pg.wait_for_timeout(a["wait"])
        return
    target = _locate(pg, a)
    if a.get("do") == "hover":
        target.hover()
    elif a.get("do") == "fill":
        target.fill(a["text"])
    else:
        target.click()
    pg.wait_for_timeout(a.get("settle", 600))


def resolve(path: str, portfolios: list[dict]) -> str:
    """Placeholders in a shot's path: {pf:NAME} → that portfolio's id, {forked:NAME} → the day it was forked."""
    by = {p["name"]: p for p in portfolios}

    def sub(m: re.Match) -> str:
        kind, name = m.group(1), m.group(2)
        if name not in by:
            raise RuntimeError(f"no demo portfolio named {name!r} (path {path})")
        return str(by[name]["id"] if kind == "pf" else by[name]["forked_at"])
    return re.sub(r"\{(pf|forked):([^}]+)\}", sub, path)


def shoot(page_for, s: dict, portfolios: list[dict]) -> Path:
    pg = page_for(s.get("viewport", "desktop"), s.get("scheme", "light"))
    pg.goto(BASE + resolve(s["path"], portfolios))
    pg.wait_for_load_state("networkidle")
    if s.get("wait_for"):
        pg.locator(s["wait_for"]).first.wait_for(state="visible", timeout=30000)
    pg.wait_for_timeout(s.get("settle", 1200))
    body = pg.locator("body").inner_text()
    for bad in ("Download market data", "Something went wrong", "Internal Server Error", "HTTP 503"):
        if bad in body and not s.get("allow_text") == bad:
            raise RuntimeError(f"{s['id']}: the page shows {bad!r} ({s['path']})")
    for a in s.get("actions", []):
        _act(pg, a)
    out = IMG / f"{s['id']}.png"
    if "clip" in s:  # one element, or the box around several (`to`: the last one)
        c = s["clip"]
        els = [_locate(pg, c)] + ([_locate(pg, c["to"])] if "to" in c else [])
        for e in els:
            e.wait_for(state="visible", timeout=15000)
        top = pg.evaluate("window.scrollY")  # bounding boxes are viewport-relative; the clip is page-relative
        boxes = [b | {"y": b["y"] + top} for b in (e.bounding_box() for e in els)]
        if c.get("to", {}).get("edge") == "top":  # stop where the `to` element starts (e.g. the next heading)
            boxes[-1] |= {"y": boxes[-1]["y"] - c.get("pad", 12) - 4, "height": 0}
        box = _union(boxes, c.get("pad", 12))
        if c.get("full_width"):
            vw = pg.viewport_size["width"]
            box |= {"x": 0, "width": vw}
        if c.get("max_height"):
            box["height"] = min(box["height"], c["max_height"])
        pg.screenshot(path=out, full_page=True, clip=box)
    else:
        pg.screenshot(path=out, full_page=s.get("full_page", False))
    pg.close()
    return out


def shots(only: list[str]) -> None:
    from playwright.sync_api import sync_playwright

    if not server_up(wait=60):
        sys.exit(f"Start the demo server first: uv run --directory .demo radar serve --port {PORT}")
    spec = load(SHOTS)["shots"]
    unknown = set(only) - {s["id"] for s in spec}
    if unknown:
        sys.exit(f"Unknown shot ids: {sorted(unknown)}")
    IMG.mkdir(parents=True, exist_ok=True)
    portfolios = httpx.get(BASE + "/api/portfolios", timeout=30).json()
    failed = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")

        def page_for(vp: str, scheme: str):
            return b.new_page(color_scheme=scheme, **VIEWPORTS[vp])

        for s in spec:
            if only and s["id"] not in only:
                continue
            try:
                out = shoot(page_for, s, portfolios)
                print(f"ok   {out.relative_to(ROOT).as_posix()}")
            except Exception as e:  # keep going: report every broken shot at once
                failed.append(s["id"])
                print(f"FAIL {s['id']}: {e}")
        b.close()
    if failed:
        sys.exit(f"{len(failed)} shot(s) failed: {', '.join(failed)}")


def explore(paths: list[str], scheme: str) -> None:
    """Full-page desktop captures of demo pages in .demo/explore/, to look at before writing shots.yaml."""
    from playwright.sync_api import sync_playwright

    if not server_up(wait=60):
        sys.exit(f"Start the demo server first: uv run --directory .demo radar serve --port {PORT}")
    out = DEMO / "explore"
    out.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        for path in paths:
            pg = b.new_page(color_scheme=scheme, viewport={"width": 1440, "height": 900})
            pg.goto(BASE + path)
            pg.wait_for_load_state("networkidle")
            pg.wait_for_timeout(1500)
            f = out / (re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_") or "home")
            pg.screenshot(path=f.with_suffix(".png"), full_page=True)
            print(f"{f.with_suffix('.png')}  ({pg.evaluate('document.documentElement.scrollHeight')} px)")
            pg.close()
        b.close()


# ---------------- pdf ----------------

FOOTER = ('<div style="font-size:8px;width:100%;text-align:center;color:#888">'
          'Market Radar · side <span class="pageNumber"></span> af <span class="totalPages"></span></div>')


def pdf() -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page(viewport={"width": 1120, "height": 900}, color_scheme="light")
        pg.goto((SITE / "index.html").as_uri())
        pg.evaluate("document.querySelectorAll('img[loading=lazy]').forEach(i => i.loading = 'eager')")
        pg.wait_for_load_state("networkidle")
        pg.evaluate("Promise.all([...document.images].map(i => i.complete ? 1 : new Promise(r => { i.onload = i.onerror = r })))")
        pg.evaluate("document.fonts.ready")
        pg.emulate_media(media="print")
        pg.pdf(path=PDF, format="A4", print_background=True, scale=0.68,
               margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"},
               display_header_footer=True, header_template="<span></span>", footer_template=FOOTER)
        b.close()
    print(f"{PDF.relative_to(ROOT).as_posix()}: {pdf_pages()} pages")


def pdf_pages() -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", PDF.read_bytes()))


# ---------------- check ----------------

def check() -> None:
    problems: list[str] = []
    html = (SITE / "index.html").read_text(encoding="utf-8")
    # the import presets' broker names are features of the app (the brochure lists them), not personal data
    presets = {re.split(r" \(", p["label"])[0] for p in load(ROOT / "src/radar/importers/presets.yaml").values() if "label" in p}
    hits = leaks.leak_check(MKT, [x for x in leaks.leak_patterns() if not any(x.lower() == n.lower() for n in presets)])
    problems += [f"leak: {h}" for h in hits]
    used = set(re.findall(r'src="img/([^"]+)"', html))
    have = {p.name for p in IMG.glob("*.png")}
    problems += [f"missing image: img/{n}" for n in sorted(used - have)]
    problems += [f"unused image: img/{n}" for n in sorted(have - used)]
    shot_ids = {s["id"] for s in load(SHOTS)["shots"]}
    problems += [f"image without a shot in shots.yaml: {n}" for n in sorted(used) if n[:-4] not in shot_ids]
    for f in load(FEATURES)["features"]:
        if f'id="{f["section"]}"' not in html:
            problems.append(f"feature {f['id']}: no element with id=\"{f['section']}\" in index.html")
        for s in f.get("shots", []):
            if s not in shot_ids:
                problems.append(f"feature {f['id']}: shot {s} not in shots.yaml")
            elif f"img/{s}.png" not in html:
                problems.append(f"feature {f['id']}: shot {s} not used in index.html")
    if DEMO.exists():
        check_demo_db()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page(viewport={"width": 390, "height": 844})
        pg.goto((SITE / "index.html").as_uri())
        w = pg.evaluate("document.documentElement.scrollWidth")
        if w > 390:
            problems.append(f"index.html scrolls sideways at 390 px (width {w})")
        b.close()
    if PDF.exists():
        print(f"PDF: {pdf_pages()} pages")
    if problems:
        print("\n".join(problems))
        sys.exit(f"{len(problems)} problem(s)")
    print("check: ok")


def edition(data_asof: str | None) -> None:
    """marketing/edition.json: what this edition covers, for the next run to diff against."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    out = {"date": date.today().isoformat(), "commit": head, "data_asof": data_asof,
           "features": [f["id"] for f in load(FEATURES)["features"]],
           "shots": [s["id"] for s in load(SHOTS)["shots"]], "pdf_pages": pdf_pages() if PDF.exists() else None}
    (MKT / "edition.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


def everything() -> None:
    workspace()
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    proc = subprocess.Popen(["uv", "run", "--directory", str(DEMO), "radar", "serve", "--port", str(PORT)], cwd=ROOT,
                            env=env, start_new_session=sys.platform != "win32")
    try:
        if not server_up(wait=120):
            sys.exit("The demo server did not start.")
        seed()
        shots([])
        pdf()
        check()
    finally:
        stop(proc)


def stop(proc: subprocess.Popen) -> None:
    """Stop the server and its children (`uv run` starts the Python process as a child)."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:
        os.killpg(proc.pid, 15)
    proc.wait(timeout=30)


def main() -> None:
    ap = argparse.ArgumentParser(description="Marketing material from a demo copy of the app.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("workspace")
    sub.add_parser("seed")
    sh = sub.add_parser("shots")
    sh.add_argument("ids", nargs="*", help="only these shot ids")
    ex = sub.add_parser("explore", help="full-page captures of demo pages in .demo/explore/")
    ex.add_argument("paths", nargs="+", help="app paths, e.g. /returns '/discover?mkt=europe'")
    ex.add_argument("--dark", action="store_true")
    sub.add_parser("pdf")
    sub.add_parser("check")
    ed = sub.add_parser("edition")
    ed.add_argument("--data-asof", help="the market data date shown in the screenshots")
    sub.add_parser("all")
    a = ap.parse_args()
    commands = {"workspace": workspace, "seed": seed, "pdf": pdf, "check": check, "all": everything,
                "shots": lambda: shots(a.ids), "explore": lambda: explore(a.paths, "dark" if a.dark else "light"),
                "edition": lambda: edition(a.data_asof)}
    commands[a.cmd]()


if __name__ == "__main__":
    main()
