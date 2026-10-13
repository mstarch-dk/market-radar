"""The radar's market-wide readings as data: regime, sector/theme rotation, momentum leaders, positioning and
data coverage. `radar run` writes them to reports/dashboard.json (via report.build); the web API serves them
from there. Charts are series of numbers here; drawing them is the frontend's job.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime

import numpy as np
import pandas as pd

from . import coverage, external, mine, snapshot, universe
from .config import REPORTS, settings, universe_config
from .ingest import load_fred, load_prices, wide
from .signals import momentum, regime, rotation

FILE_NAME = "dashboard.json"


# ---------------- helpers ----------------

def _clean(v):
    if isinstance(v, dict):
        return {str(k): _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (pd.Timestamp, date)):
        return v.isoformat()[:10]
    if v is pd.NaT or v is pd.NA:
        return None
    return v


def _records(df: pd.DataFrame) -> list[dict]:
    return [_clean(row) for row in df.to_dict("records")]


def line_chart(series: dict[str, pd.Series], title: str, decimals: int = 2, hlines=(), days: int = 756) -> dict:
    """A line chart as data: each series' last `days` points (NaNs dropped) plus reference lines."""
    out = []
    for name, s in series.items():
        s = s.dropna().iloc[-days:]
        out.append({"name": name, "dates": [d.date().isoformat() for d in pd.to_datetime(s.index)],
                    "values": [float(v) for v in s.values]})
    return {"title": title, "decimals": decimals, "hlines": [float(h) for h in hlines], "series": out}


def rrg_points(ratio: pd.DataFrame, mom: pd.DataFrame, names: dict[str, str], asof: date | None = None) -> list[dict]:
    """Each ticker's weekly path through the rotation graph; the last point is where it is now. Weekly bins are
    labelled by their Friday, so the current week's date is capped at `asof` (no date after the data)."""
    out = []
    for t in ratio.columns:
        r, m = ratio[t], mom[t]
        ok = r.notna() & m.notna()
        if not ok.any():
            continue
        r, m = r[ok], m[ok]
        out.append({"ticker": t, "name": names.get(t, t), "quadrant": rotation.quadrant(r.iloc[-1], m.iloc[-1]),
                    "tail": [{"date": min(d.date(), asof or d.date()).isoformat(), "x": float(x), "y": float(y)}
                             for d, x, y in zip(r.index, r.values, m.values)]})
    return out


def _clusters(top: pd.DataFrame, universe_df: pd.DataFrame, min_count: int, min_ratio: float) -> list[dict]:
    """Industries (then sectors) over-represented among a region's momentum leaders.

    `expected` is the count the group's share of the whole region would predict; a cluster needs at least
    `min_count` names and `min_ratio` x expected. A sector already fully covered by an industry cluster is skipped.
    """
    out, covered = [], set()
    for level in ("industry", "sector"):
        for name, g in top[top[level] != ""].groupby(level):
            base = (universe_df[level] == name).mean() * len(top)
            if len(g) < min_count or len(g) < min_ratio * base or set(g["ticker"]) <= covered:
                continue
            out.append({"level": level, "name": name, "count": len(g), "expected": round(base, 1),
                        "new": int(g["new"].sum()), "tickers": list(g["ticker"])})
            covered |= set(g["ticker"])
    return sorted(out, key=lambda c: -c["count"] / max(c["expected"], 0.5))


# ---------------- compute ----------------

ROTATION_KEYS = ("ticker", "name", "rank", "rank_change", "quadrant", "quadrant_local", "rel_r1m", "rel_r3m", "rel_r6m",
                 "r1m", "r3m", "r6m", "above200", "rs_ratio", "rs_mom", "rs_score", "ucits", "ucits_name", "isin",
                 "positive_list")
MOMENTUM_KEYS = ("ticker", "name", "sector", "industry", "rank", "score", "r1m", "r3m", "r6m", "r12_1", "from_high",
                 "vol_surge", "trend_ok", "new")
FACTSET_KEYS = ("quarter", "growth_now", "growth_start", "guidance_neg", "guidance_pos", "fwd_pe", "fwd_pe_5y",
                "fwd_pe_10y", "cy_next_growth", "rev_up_sectors", "rev_down_sectors")


@dataclass
class Computed:
    data: dict             # dashboard.json
    me: list[dict]         # holdings table (summary.json; the API recomputes it live)
    rotation: pd.DataFrame  # for the rank snapshots
    leaders: pd.DataFrame


def compute() -> Computed:
    """Every market-wide reading from local data. Reads earlier snapshots but doesn't write any."""
    cfg = settings()
    ucfg = universe_config()
    bench = universe.benchmark()
    prices = load_prices()
    if prices.empty:
        raise SystemExit("No price data yet – run `radar update` first.")
    closes, volumes = wide(prices, "close"), wide(prices, "volume")
    fred = load_fred()
    today = date.today()
    asof = closes[bench].dropna().index[-1].date()

    # --- regime
    groups = universe.stock_groups()
    labels = universe.stock_group_labels()
    ext = ucfg.get("external", {})
    cli_raw = external.load_oecd_cli()
    cli = external.cli_table(cli_raw, ext.get("oecd_cli", {})) if not cli_raw.empty else pd.DataFrame()
    fs_hist = external.load_factset()
    fs = fs_hist.iloc[-1].to_dict() if not fs_hist.empty else None
    macro = universe.macro_yahoo()
    inds, breadth = regime.indicators(closes, fred, bench, groups, labels, macro, cfg["regime"], cli, fs)
    max_age = cfg["coverage"]["max_age"]
    regime.apply_freshness(inds, asof, max_age)
    overall = regime.overall(inds)
    rg = cfg["regime"]
    b = closes[bench].dropna()
    charts = [
        line_chart({"ACWI": b, "50-day avg": b.rolling(50).mean(), "200-day avg": b.rolling(200).mean()},
                   "Global trend – MSCI ACWI"),
        line_chart(breadth, "Breadth – % of stocks above their 200-day average", 0,
                   (rg["breadth_weak"], rg["breadth_strong"])),
    ]
    if "BAMLH0A0HYM2" in fred:
        charts.append(line_chart({"HY spread %": fred["BAMLH0A0HYM2"]}, "US high-yield credit spread (%)"))
    hl = regime.net_highs_lows(closes, sorted({t for ts in groups.values() for t in ts}))
    if not hl.empty:
        band = rg["highs_lows_band"]
        charts.append(line_chart({"Net new highs %": hl}, "New 52w highs minus new lows (% of stocks, 10d avg)", 1,
                                 (-band, 0, band)))
    vix = macro["VIX"]
    if vix in closes:
        charts.append(line_chart({"VIX": closes[vix]}, "Volatility – VIX", 1, (rg["vix_calm"], rg["vix_stress"])))
    if macro.get("VIX3M") in closes:
        charts.append(line_chart({"VIX/VIX3M": closes[vix] / closes[macro["VIX3M"]]},
                                 "VIX term structure (above 1 = inverted, stress)", hlines=(1,)))
    if macro.get("Copper") in closes and macro.get("Gold") in closes:
        charts.append(line_chart({"Copper/gold": closes[macro["Copper"]] / closes[macro["Gold"]] * 1000},
                                 "Copper/gold ratio (×1000): growth vs defence"))
    if not cli_raw.empty:
        order = [a for a in ext.get("oecd_cli", {}) if a in cli_raw.columns]
        charts.append(line_chart({ext["oecd_cli"][a]: cli_raw[a] for a in order[:4]},
                                 "OECD leading indicators (100 = trend)", hlines=(100,), days=2000))

    # --- rotation (sectors, regions, themes, factors)
    insts = universe.etfs()
    rc = cfg["rotation"]
    rot = rotation.relative_table(closes, bench, insts, rc["window"], rc["tail"])
    prev_d, prev = snapshot.previous("rotation", cfg["snapshot_min_gap_days"])
    prev_rank = dict(zip(prev["ticker"], prev["rank"])) if prev is not None else {}
    rot["rank_change"] = [prev_rank[t] - r if t in prev_rank else None for t, r in zip(rot["ticker"], rot["rank"])]
    pl = universe.positive_list()
    isins, pl_year = (set(pl["isin"]), pl.attrs["year"]) if pl is not None else (None, None)
    rot["positive_list"] = [universe.positive_list_flag(i, isins) for i in rot["isin"]]
    rot["quadrant_local"] = None

    names = {i.ticker: i.name for i in insts}
    local_bench = universe.group_benchmarks()
    rot_groups = []
    for key, g in ucfg["etf_groups"].items():
        tickers = [i.ticker for i in insts if i.group == key and i.ticker in closes.columns]
        ratio, mom = rotation.rrg(closes, bench, tickers, rc["window"], rc["tail"])
        grp = {"key": key, "label": g["label"], "local_benchmark": None, "rrg": rrg_points(ratio, mom, names, asof),
               "rrg_local": None}
        lb = local_bench.get(key)
        if lb and lb["ticker"] in closes.columns and tickers:
            lratio, lmom = rotation.rrg(closes, lb["ticker"], tickers, rc["window"], rc["tail"])
            grp["local_benchmark"] = lb["name"]
            grp["rrg_local"] = rrg_points(lratio, lmom, names, asof)
            local_q = {t: rotation.quadrant(lratio[t].iloc[-1], lmom[t].iloc[-1]) for t in tickers}
            mask = rot["group"] == key
            rot.loc[mask, "quadrant_local"] = rot.loc[mask, "ticker"].map(local_q)
        grp["rows"] = [{k: r.get(k) for k in ROTATION_KEYS} for r in _records(rot[rot["group"] == key])]
        rot_groups.append(grp)

    # --- momentum
    mc = cfg["momentum"]
    lead = momentum.leaders(closes, volumes, groups, mc["min_history_days"])
    lead["name"] = lead["ticker"].map(universe.names(sorted(set(lead["ticker"]))))
    sec = universe.sectors(list(lead["ticker"]))
    lead["sector"] = lead["ticker"].map(sec["sector"])
    lead["industry"] = lead["ticker"].map(sec["industry"])
    mprev_d, mprev = snapshot.previous("momentum", cfg["snapshot_min_gap_days"])
    top_n = mc["top_n"]
    regions = []
    for region, df in lead.groupby("region"):
        top = df[df["rank"] <= top_n].copy()
        prev_top = set(mprev[(mprev["group"] == region) & (mprev["rank"] <= top_n)]["ticker"]) if mprev is not None else None
        top["new"] = [prev_top is not None and t not in prev_top for t in top["ticker"]]
        regions.append({
            "key": region, "label": labels.get(region, region),
            "rows": [{k: r.get(k) for k in MOMENTUM_KEYS} for r in _records(top)],
            "entrants": [t for t, n in zip(top["ticker"], top["new"]) if n],
            "dropped": sorted(prev_top - set(top["ticker"])) if prev_top is not None else [],
            "clusters": _clusters(top, df, cfg["sectors"]["cluster_min"], cfg["sectors"]["cluster_ratio"]),
        })

    # --- me (the API recomputes this live; summary.json needs it now)
    raw_closes = wide(prices, "raw_close") if "raw_close" in prices else None
    rot_rows = _records(rot[["ticker", "ucits", "quadrant"]])
    me = mine.table(closes, wide(prices, "high"), wide(prices, "low"), volumes, raw_closes, lead, rot_rows,
                    overall["label"], cfg)

    # --- positioning & cycle (non-price data)
    cot = external.load_cot()
    poscfg = cfg["positioning"]
    cot_tab = (external.cot_table(cot, poscfg["lookback_weeks"], poscfg["extreme_pct"])
               if not cot.empty else pd.DataFrame())
    fs_ctx = None
    if fs is not None:
        fs_ctx = _clean({k: fs.get(k) for k in FACTSET_KEYS})
        fs_ctx["report_date"] = fs["report_date"].date().isoformat()
        fs_ctx["history"] = _records(fs_hist[["report_date", "quarter", "growth_now", "fwd_pe"]].tail(12))

    # --- data sources & coverage (what the readings above are, and aren't, based on)
    h = universe.holdings()
    cot_markets = [m for grp in ext.get("cot", {}).values() for m in grp]
    cov = coverage.build(
        asof, prices, universe.all_price_tickers(offline=True), fred, universe.macro_fred(), cot, cot_markets,
        cli_raw, ext.get("oecd_cli", {}), fs_hist, external.load_analyst(),
        sorted(h.loc[h["status"].isin(["holding", "watch"]), "symbol"].dropna()) if not h.empty else [],
        sorted({t for ts in groups.values() for t in ts}), h, pl_year, inds, cfg, today)

    head = {"generated": datetime.now().isoformat(timespec="seconds"), "asof": asof.isoformat()}
    data = head | {
        "regime": {"overall": overall, "indicators": _clean(inds), "charts": charts,
                   "coverage": {"regime": cov["regime"], "oldest": cov["oldest"], "failing": cov["failing"]}},
        "rotation": {"prev": prev_d.isoformat() if prev_d else None, "tail_weeks": rc["tail"],
                     "positive_list_year": pl_year, "groups": rot_groups},
        "momentum": {"prev": mprev_d.isoformat() if mprev_d else None, "top_n": top_n, "regions": regions},
        "positioning": {"factset": fs_ctx, "cli": _records(cli) if not cli.empty else [],
                        "cot": _records(cot_tab) if not cot_tab.empty else []},
        "coverage": _clean(cov),
    }
    return Computed(data, me, rot, lead)


# ---------------- reading the stored snapshot ----------------

_cache: tuple[float, dict, str] | None = None  # (mtime, data, path)


def path():
    return REPORTS / FILE_NAME


def load() -> dict | None:
    """dashboard.json from the last `radar run`, re-read when the file changes; None if it doesn't exist."""
    global _cache
    p = path()
    if not p.exists():
        return None
    mtime = p.stat().st_mtime
    if _cache is None or _cache[0] != mtime or _cache[2] != str(p):
        _cache = (mtime, json.loads(p.read_text(encoding="utf-8")), str(p))
    return _cache[1]
