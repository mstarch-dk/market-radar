"""Your market views as the app and the skills see them: the stored views (userstore) with the radar's evidence
for each, the templates and vocabulary from config/views.yaml, and how a name lines up with your views.

These are the user's subjective beliefs. Every output that carries them says so (DISCLAIMER)."""
from __future__ import annotations

from functools import cache

import pandas as pd

from . import universe
from .config import load_yaml
from .errors import Invalid
from .signals import views as sv
from .sources import external, ingest, tracked
from .userstore import viewstore

DISCLAIMER = ("These are your own subjective beliefs about where markets are heading, not facts or forecasts. "
              "The evidence shows what the radar's data did over the last three months; it doesn't prove or "
              "disprove a view.")
SECTORS = ["Basic Materials", "Communication Services", "Consumer Cyclical", "Consumer Defensive", "Energy",
           "Financial Services", "Healthcare", "Industrials", "Real Estate", "Technology", "Utilities"]
REGIONS = ["us", "europe", "nordic", "asia"]
HORIZONS = ["3m", "6m", "12m", "3y"]
EXPOSURE_KINDS = ["etf", "sector", "industry", "region", "ticker"]


@cache
def config() -> dict:
    return load_yaml("views.yaml")


def validate(view: dict) -> dict:
    """A view as it can be stored: a statement (trimmed), conviction 1-5, a known horizon, exposures of a known
    kind with an effect of +1 or -1, and only known indicators expecting up or down; Invalid naming the first
    problem. The app's add, edit and restore and the skills' add_view all go through it."""
    v = dict(view, statement=(view.get("statement") or "").strip())
    if not v["statement"]:
        raise Invalid("A view needs a statement.")
    if not 1 <= int(v.get("conviction") or 0) <= 5:
        raise Invalid("Conviction is 1 (a hunch) to 5 (very sure).")
    if v.get("horizon") is not None and v["horizon"] not in HORIZONS:
        raise Invalid(f"Horizon is one of {', '.join(HORIZONS)}.")
    for e in v.get("exposures") or []:
        if e.get("kind") not in EXPOSURE_KINDS or not str(e.get("key") or "").strip() or e.get("effect") not in (1, -1):
            raise Invalid(f"An exposure is {{kind: {' | '.join(EXPOSURE_KINDS)}, key, effect: 1 or -1}}, not {e}.")
    if any(i.get("expect") not in ("up", "down") for i in v.get("indicators") or []):
        raise Invalid("An indicator expects up or down.")
    known = set(config()["indicators"])
    bad = [i["indicator"] for i in v.get("indicators") or [] if i["indicator"] not in known]
    if bad:
        raise Invalid(f"Unknown indicator: {', '.join(bad)}.")
    return v


def templates() -> list[dict]:
    out = []
    for t in config()["templates"]:
        out.append({**{k: t.get(k) for k in ("key", "area", "pair", "statement", "falsifier")},
                    "exposures": [{"kind": k, "key": str(v), "effect": int(e)} for k, v, e in t["exposures"]],
                    "indicators": [{"indicator": i, "expect": x} for i, x in t["indicators"]]})
    return out


def catalogue() -> dict:
    """What the editor offers: indicators, ETFs (themes, factors, regions, sectors), sectors, regions."""
    etfs = [{"ticker": e.ticker, "name": e.name, "group": e.group} for e in tracked.etfs()]
    return {"indicators": [{"key": k, "label": v["label"], "kind": v["kind"]} for k, v in config()["indicators"].items()],
            "etfs": etfs, "sectors": SECTORS, "regions": REGIONS, "horizons": HORIZONS}


def ucits_map() -> dict[str, str]:
    """UCITS listing -> the US ETF it stands in for (so VVSM.DE counts as SMH)."""
    return {e.ucits: e.ticker for e in tracked.etfs() if e.ucits}


# ---------------- evidence ----------------

def reads(closes: pd.DataFrame | None = None) -> dict[str, dict]:
    if closes is None:
        prices = ingest.load_prices()
        if prices.empty:
            return {}
        prices["date"] = pd.to_datetime(prices["date"])
        closes = ingest.wide(prices)
    return sv.readings(config()["indicators"], closes, ingest.load_fred(), external.load_oecd_cli(),
                       tracked.benchmark())


def with_evidence(status: str | None = "active", closes: pd.DataFrame | None = None) -> list[dict]:
    """Your views, each with the radar's evidence."""
    vs = viewstore.views(status)
    if not vs:
        return []
    r = reads(closes)
    return [{**v, "evidence": sv.evidence(v, r)} for v in vs]


# ---------------- alignment ----------------

def align_profile(identity: dict, closes: pd.DataFrame, views: list[dict] | None = None) -> dict | None:
    """One name against your active views (for its profile). None when you have no views."""
    views = viewstore.views("active") if views is None else views
    if not views:
        return None
    t = identity["symbol"]
    meta = pd.DataFrame([{k: identity.get(k) for k in ("sector", "industry", "region", "country")}], index=[t])
    ctx = sv.contexts([t], meta, closes, tracked.benchmark(), sv.view_etfs(views), ucits_map(), config())[t]
    out = sv.align(ctx, views, config())
    status = {v["id"]: v["evidence"]["verdict"] for v in with_evidence("active", closes)}
    for row in out["views"]:
        row["evidence"] = status.get(row["id"])
    return out


_cache: dict = {}


def reset() -> None:
    """Forget the cached evidence."""
    _cache.clear()


def align_many(tickers: list[str], store: str = "main") -> dict[str, dict]:
    """Many names against your active views (the Momentum and Discover columns), compactly. `store` says
    whose prices: the radar's own ("main") or the discovery scan's ("discovery")."""
    views = viewstore.views("active")
    if not views or not tickers:
        return {}
    key = (store, viewstore.views_version(), tuple(sorted(tickers)))
    if key in _cache:
        return _cache[key]
    bench = tracked.benchmark()
    if store == "discovery":
        from .discovery import scan

        meta = scan.load_universe().set_index("ticker")
        meta["region"] = meta["market"].map({"nordic": "nordic", "europe": "europe"})
        dp = scan.load_prices()
        main = ingest.load_prices()
        etfs = set(sv.view_etfs(views)) | {bench}
        prices = pd.concat([dp, main[main["ticker"].isin(etfs) & ~main["ticker"].isin(set(dp["ticker"]))]])
    else:
        prices = ingest.load_prices()
        sec = universe.sectors([t for t in tickers])
        from .universe import region_for

        meta = pd.DataFrame({"sector": sec["sector"], "industry": sec["industry"],
                             "region": [region_for(t) for t in sec.index], "country": None}, index=sec.index)
    prices = prices[prices["ticker"].isin(set(tickers) | set(sv.view_etfs(views)) | {bench})].copy()
    prices["date"] = pd.to_datetime(prices["date"])
    closes = ingest.wide(prices)
    if bench not in closes:
        return {}
    ctxs = sv.contexts(tickers, meta, closes, bench, sv.view_etfs(views), ucits_map(), config())
    out = {}
    for t in tickers:
        a = sv.align(ctxs.get(t) or {"ticker": t}, views, config())
        out[t] = {"label": a["label"], "score": a["score"],
                  "views": [{"id": r["id"], "label": r["label"], "reasons": [x["text"] for x in r["reasons"]]}
                            for r in a["views"] if r["label"] != "unrelated"]}
    _cache.clear()
    _cache[key] = out
    return out
