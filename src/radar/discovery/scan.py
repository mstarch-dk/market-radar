"""The discovery scan (`radar discover`, or the button on the Discover page): build the wide universe, download
about 14 months of prices for it, and write reports/discovery.json.

It is kept apart from the daily radar: its own price store (data/discovery/), its own report, and nothing here
reaches the regime vote, breadth or the momentum page. Each step is logged in data/sources.json; a failed step
keeps its cached data."""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from typing import Callable

import pandas as pd

from .. import coverage, ingest, net, ops, universe
from ..config import discovery_config, settings, write_csv, write_parquet, write_text
from ..paths import CACHE, HISTORY, REPORTS
from ..signals import discovery as sig
from . import sources

DIR = CACHE / "discovery"
UNIVERSE_FILE = DIR / "universe.csv"
ISIN_MAP_FILE = DIR / "isin_map.csv"
PRICES_FILE = DIR / "prices.parquet"
SCAN_LOCK = DIR / "scan.lock"        # one discovery scan at a time (the app's, or `radar discover` in a terminal)
SNAPSHOTS = HISTORY / "discovery" / "snapshots"
REPORT_FILE = REPORTS / "discovery.json"

Log = Callable[[str], None]
Progress = Callable[[int, int], None]
INDEX_KEEP: set[str] = set()   # index members (STOXX 600, S&P 500) found while building: never dropped as duplicates
UNIVERSE_COLS = ["ticker", "name", "market", "kind", "exchange", "country", "currency", "market_cap_dkk",
                 "sector", "industry", "category", "isin"]


# ---------------- FX ----------------

FX_NEEDED = {"EUR", "USD", "GBP", "SEK", "NOK", "CHF"}   # the discovery markets' currencies


def fx_rates() -> dict[str, float]:
    """Latest DKK rate per currency (DKK = 1): from the radar's own price store when it is recent, else Yahoo. A
    needed rate Yahoo doesn't return comes from the store at any age (a size filter doesn't mind a few weeks'
    drift); one missing from both raises, rather than leaving a whole market without market caps."""
    yf = net.yf()

    stored = ingest.load_prices()
    older: dict[str, float] = {}
    if not stored.empty:
        fx = stored[stored["ticker"].isin(universe.FX_TICKERS)].copy()
        fx["date"] = pd.to_datetime(fx["date"])
        last = fx.sort_values("date").groupby("ticker").last()
        recent = last[last["date"] >= pd.Timestamp.today().normalize() - pd.Timedelta(days=7)]
        out = universe.dkk_rates(recent["close"].astype(float).to_dict())
        if FX_NEEDED <= set(out):   # a rate still missing (e.g. a new currency) leaves those caps unknown
            return out
        older = universe.dkk_rates(last["close"].astype(float).to_dict())
    raw = sources.retry(lambda: yf.download(universe.FX_TICKERS, period="10d", auto_adjust=False,
                                            progress=False, group_by="ticker"))
    last = {}
    for t in universe.FX_TICKERS:
        try:
            s = raw[t]["Close"].dropna()
        except KeyError:
            continue
        if len(s):
            last[t] = float(s.iloc[-1])
    out = universe.dkk_rates(last)
    if len(out) < 4 and not older:
        raise RuntimeError("no FX rates from Yahoo")
    out = {c: r for c, r in older.items() if c not in out} | out
    missing = sorted(FX_NEEDED - set(out))
    if missing:
        raise RuntimeError(f"no DKK rate for {', '.join(missing)} from Yahoo or the stored prices: "
                           "those markets' caps would be unknown")
    return out


# ---------------- universe ----------------

def load_universe() -> pd.DataFrame:
    if not UNIVERSE_FILE.exists():
        return pd.DataFrame(columns=UNIVERSE_COLS)
    return pd.read_csv(UNIVERSE_FILE, keep_default_na=False, na_values={"market_cap_dkk": [""]})


def _stocks(key: str, mk: dict, fx: dict[str, float], log: Log) -> pd.DataFrame:
    """A stock market: Yahoo's screener on its exchanges, plus every member of its index (if any), any size.
    With `members_only` the screener only supplies the members' market caps; sectors then come from the index
    file (a sector screen of the big US exchanges would cost hundreds of calls)."""
    min_cap = mk.get("screen_min_cap", 5e7)
    quotes = {code: sources.screen_exchange(code, min_cap) for code in mk["exchanges"]}
    keep, members, what = set(), None, None
    if mk.get("index"):
        what = sources.INDEXES[mk["index"]][2]
        members = sources.fetch_index(mk["index"])
        if not mk.get("members_only"):           # Nordic STOXX members belong to the Nordic market
            members = members[members["exchange"].isin(mk["exchanges"])]
        keep = set(members["ticker"])
        INDEX_KEEP.update(keep)
    if mk.get("members_only"):
        if members is None:
            raise ValueError(f"{mk['label']}: members_only needs an index")
        quotes = {code: [q for q in qs if q.get("symbol") in keep] for code, qs in quotes.items()}
    df = sources.home_listings(quotes, fx, mk.get("min_cap_dkk", 0), keep)
    if not mk.get("members_only"):
        sources.check_counts(df, mk.get("min_count"), mk["label"])
    hints = {}
    if members is not None:
        screened = {q.get("symbol") for qs in quotes.values() for q in qs}
        extra = members[~members["ticker"].isin(screened)]
        log(f"  {len(members)} {what} members, {len(extra)} of them not in Yahoo's screener (kept, size unknown)")
        df = pd.concat([df, extra.drop(columns="sector_hint")], ignore_index=True)
        hints = dict(zip(members["ticker"], members["sector_hint"]))
    df["kind"] = "stock"
    secs = {} if mk.get("members_only") else sources.screen_sectors(mk["exchanges"])
    df["sector"] = df["ticker"].map(secs).fillna(df["ticker"].map(hints)).fillna("")
    return df


def _etfs(mk: dict, cfg: dict, log: Log, progress: Progress | None) -> pd.DataFrame:
    pl = universe.positive_list()
    if pl is None:
        raise RuntimeError("no positive list: save SKAT's list as imports/positivliste.xlsx")
    funds = sources.positive_list_funds(pl)
    cached = pd.read_csv(ISIN_MAP_FILE, keep_default_na=False) if ISIN_MAP_FILE.exists() else pd.DataFrame(
        columns=["isin", "symbol", "exchange", "yahoo_name", "quote_type"])
    todo = len(set(funds["isin"]) - set(cached["isin"]))
    if todo:
        n = min(todo, cfg["isin_lookups_per_scan"])
        log(f"  looking up {n} of {todo} new positive-list ISINs on Yahoo (cached; the rest on later scans)…")
    isin_map = sources.map_isins(list(funds["isin"]), cached, cfg["etf_exchanges"], progress=progress,
                                 budget=cfg["isin_lookups_per_scan"])
    DIR.mkdir(parents=True, exist_ok=True)
    write_csv(isin_map, ISIN_MAP_FILE, index=False)
    picked = sources.pick_share_classes(funds, isin_map, cfg["etf_exchanges"])
    if len(picked) < mk.get("min_count", 0):
        raise ValueError(f"only {len(picked)} positive-list ETFs found on Yahoo (expected ≥ {mk['min_count']})")
    names = [y or s for y, s in zip(picked["yahoo_name"], picked["sub_fund"])]
    return pd.DataFrame({
        "ticker": picked["symbol"], "name": names, "kind": "etf", "exchange": picked["exchange"],
        "country": None, "currency": None, "market_cap_dkk": None, "isin": picked["isin"],
        "category": [sources.etf_category(f"{n} {s}", cfg["etf_categories"]) for n, s in zip(names, picked["sub_fund"])],
    })


def build_universe(log: Log = print, progress: Progress | None = None) -> pd.DataFrame:
    """Every market's names, from scratch. A market that fails keeps its cached rows (and is reported)."""
    cfg = discovery_config()
    fx = fx_rates()
    cached = load_universe()
    frames, failed = [], []
    for key, mk in cfg["markets"].items():
        try:
            df = _etfs(mk, cfg, log, progress) if mk["kind"] == "etf" else _stocks(key, mk, fx, log)
            df["market"] = key
            log(f"  {mk['label']}: {len(df)} names")
            frames.append(df)
        except Exception as e:
            old = cached[cached["market"] == key]
            failed.append(f"{mk['label']} ({type(e).__name__}: {e})")
            log(f"  {mk['label']}: FAILED ({type(e).__name__}: {e}); keeping {len(old)} cached names")
            if not old.empty:
                frames.append(old)
    if not frames:
        raise RuntimeError("no market could be built: " + "; ".join(failed))
    # a company in two stock markets (e.g. a Nordic name's German listing) stays only in the first one
    stocks, seen = [], []
    for f in frames:
        if not f.empty and (f["kind"] == "stock").all():
            f = sources.drop_known_names(f, seen, keep=set(f["ticker"]) & INDEX_KEEP)
            seen += list(f["name"])
        stocks.append(f)
    frames = stocks
    df = pd.concat(frames, ignore_index=True).drop_duplicates("ticker")

    # quote currencies for ETFs (a cached Yahoo lookup shared with the radar); industries only where the radar
    # already knows them (one profile call per company would hit Yahoo's rate limit)
    need_ccy = df.loc[df["currency"].isna() | (df["currency"] == ""), "ticker"].tolist()
    if need_ccy:
        log(f"  looking up quote currencies for {len(need_ccy)} ETFs (cached)…")
        cur = universe.currencies(need_ccy)
        df.loc[df["ticker"].isin(need_ccy), "currency"] = df["ticker"].map(cur)
    known = CACHE / "sectors.csv"
    ind = pd.read_csv(known, keep_default_na=False).set_index("ticker")["industry"] if known.exists() else pd.Series(dtype=str)
    df["industry"] = df["ticker"].map(ind).fillna("")
    for col in ("sector", "category"):
        df[col] = df[col].fillna("") if col in df else ""
    df = df.reindex(columns=UNIVERSE_COLS)
    DIR.mkdir(parents=True, exist_ok=True)
    write_csv(df, UNIVERSE_FILE, index=False)
    if failed:
        raise PartialFailure(f"{len(df)} names; failed: {'; '.join(failed)}")
    return df


PartialFailure = coverage.PartialFailure   # the universe was built, but some market failed and kept its cached names


def universe_age_days() -> float | None:
    return (time.time() - UNIVERSE_FILE.stat().st_mtime) / 86400 if UNIVERSE_FILE.exists() else None


# ---------------- prices ----------------

def load_prices() -> pd.DataFrame:
    return pd.read_parquet(PRICES_FILE) if PRICES_FILE.exists() else pd.DataFrame(columns=ingest.COLUMNS)


def update_prices(tickers: list[str], progress: Progress | None = None, log: Log = print, sleep=time.sleep,
                  waits: tuple[int, ...] = (60, 180), today: date | None = None) -> dict:
    """Re-download the whole window (cheap at this length, and always consistently adjusted). Names Yahoo
    refused (rate limit) are asked for again after a pause, twice."""
    start = (today or date.today()) - timedelta(days=discovery_config()["history_days"])
    frames = [ingest._download(tickers, start, progress)]
    for wait in waits:
        missing = sorted(set(tickers) - set(pd.concat(frames)["ticker"]))
        if not missing or len(missing) < 0.02 * len(tickers):
            break
        log(f"  {len(missing)} names got no prices (Yahoo's rate limit?): trying again in {wait} s…")
        sleep(wait)
        frames.append(ingest._download(missing, start, progress))
    df = ingest._norm_dates(pd.concat(frames, ignore_index=True)).drop_duplicates(["ticker", "date"], keep="last")
    got = set(df["ticker"])
    if len(got) < 0.5 * len(tickers):
        raise RuntimeError(f"prices for only {len(got)} of {len(tickers)} names; keeping the previous download")
    # names Yahoo didn't return this time keep their stored bars in the window (marked stale by their last date)
    old = load_prices()
    kept = pd.DataFrame(columns=ingest.COLUMNS)
    if not old.empty:
        old["date"] = pd.to_datetime(old["date"])
        kept = old[old["ticker"].isin(set(tickers) - got) & (old["date"] >= pd.Timestamp(start))]
    if not kept.empty:
        df = pd.concat([df, kept], ignore_index=True)
    write_parquet(df.sort_values(["ticker", "date"]), PRICES_FILE, index=False)
    return {"requested": len(tickers), "got": len(got), "missing": sorted(set(tickers) - got),
            "kept": sorted(set(kept["ticker"]))}


# ---------------- report ----------------

def _wide(prices: pd.DataFrame, field: str) -> pd.DataFrame:
    return prices.pivot(index="date", columns="ticker", values=field).sort_index()


def build_report(fx: dict[str, float] | None = None) -> dict:
    from ..jsonsafe import clean as _clean

    cfg = discovery_config()
    meta = load_universe()
    prices = load_prices()
    if meta.empty or prices.empty:
        raise RuntimeError("no discovery universe or prices yet: run `radar discover`")
    prices["date"] = pd.to_datetime(prices["date"])
    closes = _wide(prices, "close").ffill(limit=5)
    raw = _wide(prices, "raw_close")
    volumes = _wide(prices, "volume")
    bench = universe.benchmark()
    asof = closes[bench].dropna().index[-1] if bench in closes else closes.index[-1]
    fx = fx or universe.dkk_rates({t: float(closes[t].dropna().iloc[-1]) for t in universe.FX_TICKERS
                                   if t in closes and closes[t].notna().any()})
    tracked = set(universe.all_price_tickers(offline=True))
    s = settings()
    df = sig.compute(closes, raw, volumes, meta, bench, fx, tracked, cfg, s["momentum"]["min_history_days"], asof,
                     s["rotation"]["window"])
    df = df.merge(meta.drop(columns=["market"]), on="ticker", how="left")
    isins = universe.positive_list_isins()
    df["positive_list"] = [universe.positive_list_flag(i, isins) if k == "etf" else None
                           for i, k in zip(df["isin"], df["kind"])]
    df["spark"] = [sig.sparkline(closes[t]) for t in df["ticker"]]
    keys = ["ticker", "name", "kind", "exchange", "country", "currency", "sector", "industry", "category", "isin",
            "positive_list", "market_cap_dkk", "size", "liquidity_dkk", "thin", "score", "score_prev", "d_score",
            "r1w", "r1m", "r3m", "r6m", "r12_1", "from_high", "vol_surge", "trend_ok", "new_high", "trend_turn", "rs_high",
            "quadrant", "off_radar", "check_data", "stale", "spark"]
    markets = []
    for key, mk in cfg["markets"].items():
        part = df[df["market"] == key].sort_values("score", ascending=False, na_position="last")
        rows = [{k: _clean(r.get(k)) for k in keys} for r in part.to_dict("records")]
        for r in rows:   # text columns: empty means unknown
            for k in ("exchange", "country", "currency", "sector", "industry", "category", "isin"):
                r[k] = r[k] or None
        markets.append({"key": key, "label": mk["label"], "kind": mk["kind"],
                        "names": int((meta["market"] == key).sum()), "scored": int(part["score"].notna().sum()),
                        "rows": rows})
    data = {"generated": datetime.now().isoformat(timespec="seconds"), "asof": asof.date().isoformat(),
            "universe_asof": datetime.fromtimestamp(UNIVERSE_FILE.stat().st_mtime).date().isoformat(),
            "markets": markets,
            "thresholds": {"size_large_dkk": cfg["size_dkk"]["large"], "size_mid_dkk": cfg["size_dkk"]["mid"],
                           "liquidity_floor_dkk": cfg["liquidity_floor_dkk"]}}
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_text(REPORT_FILE, json.dumps(data, separators=(",", ":"), allow_nan=False))
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    write_parquet(df[["ticker", "market", "score"]], SNAPSHOTS / f"{date.today().isoformat()}.parquet", index=False)
    return {"asof": data["asof"], "names": len(df), "scored": int(df["score"].notna().sum())}


def load_report() -> dict | None:
    try:
        return json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


# ---------------- the whole scan ----------------

def run(log: Log = print, progress: Progress | None = None, refresh_universe: bool = False) -> dict:
    """Universe (when older than `universe_max_age_days`, or asked), prices, report. Steps are logged in
    data/sources.json; a failing step keeps its cached data. One scan at a time (`locks.Busy` otherwise)."""
    from .. import locks

    with locks.file_lock(SCAN_LOCK, timeout=0,
                         what="a discovery scan is already running (in the app or in a terminal): wait for it to finish"):
        return _run(log, progress, refresh_universe)


def _run(log: Log, progress: Progress | None, refresh_universe: bool) -> dict:
    cfg = discovery_config()
    t0 = time.time()
    age = universe_age_days()
    if refresh_universe or age is None or age > cfg["universe_max_age_days"]:
        log("Building the discovery universe (Yahoo screener, STOXX 600, positive list)…")
        try:
            with ops.context(source="discovery_universe"):
                df = build_universe(log, progress)
            coverage.record("discovery_universe", True, f"{len(df)} names")
        except PartialFailure as e:
            coverage.record("discovery_universe", False, error=str(e), exc=e)
        except Exception as e:
            coverage.record("discovery_universe", False, error=f"{type(e).__name__}: {e}", exc=e)
            if load_universe().empty:
                raise
            log(f"Universe: FAILED ({type(e).__name__}: {e}); using the cached list.")
    meta = load_universe()
    tickers = sorted(set(meta["ticker"]) | {universe.benchmark()} | set(universe.FX_TICKERS))
    log(f"Downloading prices for {len(tickers)} names…")
    try:
        with ops.context(source="discovery_prices"):
            res = update_prices(tickers, progress, log)
        msg = f"{res['got']} of {res['requested']} names" + (
            f"; kept the stored prices of {len(res['kept'])} Yahoo didn't return" if res.get("kept") else "")
        coverage.record("discovery_prices", True, msg + (f"; no data for {len(res['missing'])}" if res["missing"] else ""))
        log(f"Prices: {msg}.")
    except Exception as e:
        coverage.record("discovery_prices", False, error=f"{type(e).__name__}: {e}", exc=e)
        log(f"Prices: FAILED ({type(e).__name__}: {e}); using the previous download.")
    out = build_report()
    log(f"Discovery: {out['scored']} of {out['names']} names scored (data as of {out['asof']}) in "
        f"{round(time.time() - t0)} s.")
    return out
