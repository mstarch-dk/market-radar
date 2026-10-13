"""Everything the radar knows about one ticker: price development, momentum, technicals, stop levels,
analyst estimates, valuation, ETF look-through and peers. Used by `radar info` and the web app.

Every section carries `status` (ok | stale | missing), `asof` and `source`, so a reader can tell a real
zero from absent data. Numbers come from the same functions the dashboard uses; nothing is invented when
a source has no answer.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from . import external, ingest, universe
from .config import PRICES_FILE, REPORTS, settings, universe_config
from .report import _fx_to_dkk, _pct_vs
from .signals import levels, momentum, rotation, technicals

OK, STALE, MISSING = "ok", "stale", "missing"
WINDOWS = {"r1w": 5, "r1m": 21, "r3m": 63, "r6m": 126, "r1y": 252}
REGION_SUFFIXES = {
    "nordic": (".CO", ".ST", ".OL", ".HE", ".IC"),
    "europe": (".DE", ".F", ".PA", ".AS", ".BR", ".L", ".MI", ".SW", ".MC", ".LS", ".VI", ".IR", ".WA"),
    "asia": (".T", ".HK", ".TW", ".TWO", ".KS", ".KQ", ".SS", ".SZ", ".SI", ".AX", ".NS", ".BO"),
}


class TickerNotFound(LookupError):
    pass


# ---------------- market data, loaded once ----------------

@dataclass
class Market:
    """The price store as wide frames, plus derived tables that are expensive to recompute per ticker."""
    prices: pd.DataFrame
    closes: pd.DataFrame
    highs: pd.DataFrame
    lows: pd.DataFrame
    volumes: pd.DataFrame
    mtime: float = 0.0
    _leaders: pd.DataFrame | None = field(default=None, repr=False)
    _isins: tuple | None = field(default=None, repr=False)

    @classmethod
    def load(cls) -> Market:
        prices = ingest.load_prices()
        if prices.empty:
            raise SystemExit("No price data yet – run `radar update` first.")
        prices["date"] = pd.to_datetime(prices["date"])
        return cls(prices, ingest.wide(prices), ingest.wide(prices, "high"), ingest.wide(prices, "low"),
                   ingest.wide(prices, "volume"), PRICES_FILE.stat().st_mtime if PRICES_FILE.exists() else 0.0)

    def bars(self, ticker: str) -> pd.DataFrame:
        """The ticker's own sessions, as Yahoo delivered them. The wide frames forward-fill gaps (right for
        return windows); anything shown as a session (last price, day change, recent bars, chart) uses these."""
        return self.prices[self.prices["ticker"] == ticker].set_index("date").sort_index()

    def stale(self) -> bool:
        return PRICES_FILE.exists() and PRICES_FILE.stat().st_mtime != self.mtime

    def leaders(self) -> pd.DataFrame:
        """Momentum metrics and scores for every tracked stock (as on the dashboard), with sectors."""
        if self._leaders is None:
            lead = momentum.leaders(self.closes, self.volumes, universe.stock_groups(offline=True),
                                    settings()["momentum"]["min_history_days"])
            sec = universe.sectors(list(lead["ticker"]))
            self._leaders = lead.assign(sector=lead["ticker"].map(sec["sector"]),
                                        industry=lead["ticker"].map(sec["industry"]))
        return self._leaders

    def positive_list(self) -> set[str] | None:
        if self._isins is None:
            try:
                self._isins = (universe.positive_list_isins(),)
            except Exception:
                self._isins = (None,)
        return self._isins[0]


def ensure_prices(ticker: str, market: Market | None = None) -> Market:
    """Make sure `ticker` has a current history. Untracked tickers are downloaded (and kept in the price
    store, so the next lookup is fast) but are not added to the daily update."""
    market = market or Market.load()
    bench = universe.benchmark()
    tracked = ticker in set(universe.all_price_tickers(offline=True))
    have = ticker in market.closes.columns
    behind = have and market.closes[ticker].dropna().index[-1] < market.closes[bench].dropna().index[-1]
    if not have or (behind and not tracked):
        ingest.update_prices([ticker])
        market = Market.load()
    if ticker not in market.closes.columns or market.closes[ticker].dropna().empty:
        raise TickerNotFound(f"No Yahoo price data for {ticker}")
    return market


# ---------------- helpers ----------------

def clean(v):
    """JSON-safe: numpy → python, NaN/inf → None, timestamps → ISO dates, recursively."""
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v]
    if isinstance(v, np.generic):
        v = v.item()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, (pd.Timestamp, date)):
        return v.isoformat()[:10]
    if v is pd.NaT or v is pd.NA:
        return None
    return v


def _ret(s: pd.Series, n: int) -> float | None:
    s = s.dropna()
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1) if len(s) > n else None


def _ret_since(s: pd.Series, start: pd.Timestamp) -> float | None:
    s = s.dropna()
    base = s[:start]
    return float(s.iloc[-1] / base.iloc[-1] - 1) if not base.empty else None


def _windows(s: pd.Series, end) -> dict[str, float | None]:
    """Returns over each window, ending on `end` (the ticker's last bar), plus year to date."""
    s = s.dropna()[:end]
    out = {k: _ret(s, n) for k, n in WINDOWS.items()}
    out["ytd"] = _ret_since(s, pd.Timestamp(year=pd.Timestamp(end).year, month=1, day=1) - pd.Timedelta(days=1))
    return out


def _diff(a: dict, b: dict) -> dict:
    return {k: (a[k] - b[k]) if a.get(k) is not None and b.get(k) is not None else None for k in a}


def region_for(ticker: str) -> str:
    for region, tickers in universe.stock_groups(offline=True).items():
        if ticker in tickers:
            return region
    for region, suffixes in REGION_SUFFIXES.items():
        if ticker.upper().endswith(suffixes):
            return region
    return "us"


def sector_etf(region: str, sector: str | None, industry: str | None) -> str | None:
    cfg = universe_config().get("sector_etfs") or {}
    m = cfg.get("europe" if region in ("europe", "nordic") else region) or {}
    for prefix, etf in (m.get("industries") or {}).items():
        if industry and industry.startswith(prefix):
            return etf
    return m.get(sector) if sector else None


def _regime() -> dict:
    path = REPORTS / "summary.json"
    if not path.exists():
        return {"label": None, "asof": None}
    s = json.loads(path.read_text(encoding="utf-8"))
    return {"label": s["regime"]["label"], "asof": s.get("asof"), "net": s["regime"].get("net")}


def _section(status: str, source: str, asof=None, **data) -> dict:
    return {"status": status, "source": source, "asof": asof, **data}


# ---------------- the profile ----------------

def build(ticker: str, market: Market | None = None, refresh: bool = False) -> dict:
    """The full profile of `ticker` (a Yahoo symbol). Raises TickerNotFound without price data."""
    cfg = settings()
    market = ensure_prices(ticker, market)
    closes = market.closes
    bench = universe.benchmark()
    close = closes[ticker].dropna()
    own = market.bars(ticker)
    last_date = own.index[-1]
    b = closes[bench].dropna()
    notes: list[str] = []

    raw, raw_status = external.detail(ticker, cfg.get("profile", {}).get("max_age_hours", 24), refresh)
    info = (raw or {}).get("info") or {}
    if raw_status != OK:
        notes.append("Yahoo fundamentals and estimates: " + ("no data" if raw is None else
                     f"couldn't refresh, showing data from {raw['fetched'][:10]}"))
    detail_asof = raw["fetched"][:10] if raw else None

    is_fund = info.get("quoteType") in ("ETF", "MUTUALFUND")
    look = external.parse_fund((raw or {}).get("fund") or {}, info) if is_fund else None

    # --- identity
    h = universe.holdings()
    mine = h[h["symbol"] == ticker]
    status = mine.iloc[0]["status"] if len(mine) else None
    etf_cfg = next((e for e in universe.etfs() if ticker in (e.ticker, e.ucits)), None)
    region = etf_cfg.region.lower() if etf_cfg else region_for(ticker)
    sec = universe.sectors([ticker]) if info.get("quoteType", "EQUITY") == "EQUITY" else None
    sector = info.get("sector") or (sec.loc[ticker, "sector"] if sec is not None else "") or None
    industry = info.get("industry") or (sec.loc[ticker, "industry"] if sec is not None else "") or None
    if look and look["sector_weights"] and look["sector_weights"][0]["weight"] >= 0.5:
        sector = look["sector_weights"][0]["sector"]       # a sector fund: compare it with that sector
    currency = info.get("currency") or universe.currencies([ticker])[ticker]
    tracked = ticker in set(universe.all_price_tickers(offline=True))
    groups = universe.stock_groups(offline=True)
    isin = etf_cfg.isin if etf_cfg else None
    identity = _section(OK, "Yahoo Finance, config", detail_asof,
        symbol=ticker, name=info.get("longName") or info.get("shortName") or universe.names([ticker])[ticker],
        quote_type=info.get("quoteType") or ("ETF" if etf_cfg else None), currency=currency,
        exchange=info.get("fullExchangeName") or info.get("exchange"), country=info.get("country"),
        sector=sector, industry=industry, website=info.get("website"),
        summary=info.get("longBusinessSummary"), employees=info.get("fullTimeEmployees"),
        region=region, tracked=tracked,
        stock_group=next((g for g, ts in groups.items() if ticker in ts), None),
        etf_group=etf_cfg.group if etf_cfg else None, ucits=etf_cfg.ucits if etf_cfg else None,
        isin=isin, positive_list=universe.positive_list_flag(isin, market.positive_list()) if etf_cfg else None,
        my_status=status,
        my_position=clean(mine.iloc[0][["quantity", "avg_price", "first_trade"]].to_dict()) if status == "holding" else None)
    if not tracked:
        notes.append("Not tracked by the radar: prices are fetched on lookup, not in the daily update")

    # --- price development
    fx = _fx_to_dkk(closes, currency)
    local = _windows(close, last_date)
    dkk = _windows((close * fx.reindex(close.index).ffill()).dropna(), last_date) if fx is not None else None
    if fx is None:
        notes.append(f"No DKK rate for currency {currency}: DKK returns not shown")
    vs_acwi = _diff(local, _windows(b, last_date))
    # a fund is compared with the US sector ETF of its dominant sector (the deepest, cleanest sector series)
    setf = sector_etf("us" if look else region, sector, industry) if not etf_cfg else None
    vs_sector = (_diff(local, _windows(closes[setf], last_date))
                 if setf and setf in closes and closes[setf].notna().any() else None)
    year = close.iloc[-252:]
    recent = own.iloc[-21:]
    age = (pd.Timestamp(b.index[-1]) - last_date).days
    price = _section(OK if age <= cfg["coverage"]["max_age"]["prices"] else STALE, "Yahoo Finance (adjusted closes)",
        last_date,
        last=float(own["close"].iloc[-1]), traded_last=float(own["raw_close"].iloc[-1]),
        change_1d=_ret(own["close"], 1), currency=currency,
        returns=local, returns_dkk=dkk, vs_acwi=vs_acwi, sector_etf=setf, vs_sector=vs_sector,
        high_52w=float(year.max()), low_52w=float(year.min()),
        from_high=float(close.iloc[-1] / year.max() - 1), from_low=float(close.iloc[-1] / year.min() - 1),
        recent=[{"date": d, "close": float(r.close), "change": float(r.close / recent["close"].iloc[i - 1] - 1),
                 "volume": None if pd.isna(r.volume) else float(r.volume)}
                for i, (d, r) in enumerate(recent.iterrows()) if i > 0][::-1])
    if price["status"] == STALE:
        notes.append(f"Last price is from {last_date.date()}, {age} days before the benchmark's last close")

    # --- momentum: score within the region, as on the dashboard
    mc = cfg["momentum"]
    m = momentum.metrics(closes, market.volumes, [ticker], mc["min_history_days"]).iloc[0].to_dict()
    lead = market.leaders()
    in_group = lead[(lead["ticker"] == ticker) & (lead["region"] == region)]
    pool = lead[lead["region"] == region] if region in set(lead["region"]) else lead[lead["region"] == "us"]
    if not in_group.empty:
        r = in_group.iloc[0]
        score, rank, basis = r["score"], int(r["rank"]) if pd.notna(r["rank"]) else None, "rank in its stock group"
    else:
        score, rank = _pct_vs(pool, pd.Series(m)), None
        basis = f"percentile against the {pool['region'].iloc[0] if len(pool) else region} stock group (not a member)"
    mom = _section(OK, "radar (prices)", last_date, **{k: v for k, v in m.items() if k != "ticker"},
                   score=score, rank=rank, group_size=int(len(pool)), score_basis=basis,
                   region_label=universe.stock_group_labels().get(pool["region"].iloc[0]) if len(pool) else None)

    # --- technicals
    oc = own["close"].dropna()                         # same bars as the chart, so card and chart agree
    ma = technicals.macd(oc).iloc[-1]
    bb = technicals.bollinger(oc).iloc[-1]
    rsi = technicals.rsi(oc).iloc[-1]
    atr = (levels.atr(market.highs[ticker], market.lows[ticker], closes[ticker], cfg["stops"]["atr_days"]).dropna()
           if ticker in market.highs else pd.Series(dtype=float))
    beta, corr = technicals.beta_corr(close, b)
    tech = _section(OK, "radar (prices)", last_date,
        rsi14=rsi, rsi_state=None if pd.isna(rsi) else "overbought" if rsi >= 70 else "oversold" if rsi <= 30 else "neutral",
        macd=ma["macd"], macd_signal=ma["signal"], macd_hist=ma["hist"],
        macd_state=None if pd.isna(ma["hist"]) else "bullish" if ma["hist"] > 0 else "bearish",
        bb_pct_b=bb["pct_b"], bb_upper=bb["upper"], bb_lower=bb["lower"],
        atr=float(atr.iloc[-1]) if not atr.empty else None,
        atr_pct=float(atr.iloc[-1] / close.iloc[-1]) if not atr.empty else None,
        vol_3m=technicals.realised_vol(oc, 63), max_drawdown_1y=technicals.max_drawdown(oc),
        beta_acwi=beta, corr_acwi=corr)

    # --- analyst: stored history (tracked names) plus today's fetch, in the radar's price units
    hist = external.load_analyst()
    hist = hist[hist["ticker"] == ticker] if not hist.empty else hist
    today_row = external.parse_analyst(info) if info else None
    if today_row and raw:
        hist = pd.concat([hist, pd.DataFrame([today_row | {"ticker": ticker,
                                                           "fetched": pd.Timestamp(raw["fetched"][:10])}])],
                         ignore_index=True)
        for col in ("current_price", "target_mean", "target_median", "target_high", "target_low", "n_analysts", "rec_mean"):
            hist[col] = pd.to_numeric(hist[col], errors="coerce")
        hist = hist.drop_duplicates(["ticker", "fetched"], keep="last")
    view = levels.analyst_view(hist, ticker, close, max_age_days=cfg["coverage"]["max_age"]["analyst"]) if not hist.empty else None
    recs = external.parse_recommendations((raw or {}).get("recommendations") or [])
    eps = external.parse_eps_trend(*((raw or {}).get(k) or {} for k in ("eps_trend", "eps_revisions", "growth_estimates")))
    cal = external.parse_calendar((raw or {}).get("calendar") or {})
    has_analyst = bool(view and view.get("target_mean")) or bool(recs) or bool(eps)
    analyst = _section(raw_status if has_analyst else MISSING, "Yahoo Finance", detail_asof,
                       **(view or {}), recommendations=recs, eps=eps, calendar=cal)

    # --- stop / take-profit levels (the same rule as for holdings)
    row = m | {"score": None if score is None or pd.isna(score) else score}
    regime = _regime()
    lv = levels.for_ticker(ticker, closes, market.highs, market.lows, row,
                           mine.iloc[0]["first_trade"] if status == "holding" else None, regime["label"], hist,
                           cfg["stops"] | {"analyst_max_age_days": cfg["coverage"]["max_age"]["analyst"]})
    if lv:
        lv.pop("analyst", None)
    lvl = _section(OK if lv else MISSING, "radar (prices, analyst targets)", last_date,
                   **(lv or {}), regime=regime["label"])

    # --- fundamentals
    fund = external.parse_fundamentals(info)          # all keys, None where Yahoo has nothing
    if fund.get("market_cap") and currency != "GBp" and fx is not None:
        fund["market_cap_dkk"] = fund["market_cap"] * float(fx.iloc[-1])
    fundamentals = _section((raw_status if any(v is not None for k, v in fund.items() if k not in ("notes", "currency", "financial_currency")) else MISSING),
                            "Yahoo Finance", detail_asof, **fund, beta_radar=beta)

    # --- ETF look-through
    etf = None
    if look is not None:
        f = look
        held = set(h.loc[h["status"] == "holding", "symbol"]) if not h.empty else set()
        f["overlap"] = [x["symbol"] for x in f["top_holdings"] if x.get("symbol") in held]
        etf = _section(raw_status if f["top_holdings"] or f["expense_ratio"] else MISSING, "Yahoo Finance", detail_asof, **f)

    # --- peers and sector rotation
    peers = []
    if industry:
        same = lead[(lead["industry"] == industry) & (lead["ticker"] != ticker)].sort_values("score", ascending=False)
        names = universe.names(list(same["ticker"].head(12))) if not same.empty else {}
        peers = [{"ticker": r.ticker, "name": names.get(r.ticker, r.ticker), "region": r.region, "score": r.score,
                  "r3m": r.r3m, "r6m": r.r6m, "trend_ok": r.trend_ok, "from_high": r.from_high}
                 for r in same.head(12).itertuples()]
    rot = None
    target = setf or (ticker if etf_cfg else None)
    if target and target in closes:
        inst = next((e for e in universe.etfs() if e.ticker == target), None) or universe.Instrument(
            target, target, "sector", region)
        t = rotation.relative_table(closes, bench, [inst], settings()["rotation"]["window"], settings()["rotation"]["tail"])
        if not t.empty:
            r = t.iloc[0]
            rot = {"ticker": target, "name": inst.name, "quadrant": r["quadrant"], "rs_ratio": r["rs_ratio"],
                   "rs_mom": r["rs_mom"], "rel_r3m": r["rel_r3m"]}
    peer_sec = _section(OK if peers or rot else MISSING, "radar (prices, Yahoo sectors)", last_date,
                        industry=industry, peers=peers, rotation=rot)

    for s in (fund, etf or {}):
        notes += s.get("notes") or []
    out = {"symbol": ticker, "generated": pd.Timestamp.now().isoformat(timespec="seconds"),
           "identity": identity, "price": price, "momentum": mom, "technicals": tech, "levels": lvl,
           "analyst": analyst, "fundamentals": fundamentals, "etf": etf, "peers": peer_sec,
           "context": {"regime": regime, "notes": notes, "errors": (raw or {}).get("errors") or {}}}
    return clean(out)


def legacy_info(p: dict) -> dict:
    """The flat keys `radar info` has always printed (used by /research), followed by the full profile."""
    m = p["momentum"]
    flat = {k: m.get(k) for k in ("last", "r1m", "r3m", "r6m", "r12_1", "from_high", "sma50", "sma200", "vol_surge",
                                   "above50", "above200", "trend_ok")}
    flat |= {"ticker": p["symbol"], "name": p["identity"]["name"], "currency": p["identity"]["currency"]}
    flat |= {f"rel_{k}": p["price"]["vs_acwi"].get(k) for k in ("r1m", "r3m", "r6m")}
    if p["identity"]["stock_group"]:
        flat |= {"region": p["identity"]["stock_group"], "score_in_region": m["score"], "rank_in_region": m["rank"],
                 "region_size": m["group_size"]}
    flat["my_status"] = p["identity"]["my_status"]
    return flat | p


# ---------------- chart series ----------------

def series(ticker: str, market: Market, days: int = 756) -> dict:
    """Daily series for the charts, computed on the full history and then cut to the last `days`."""
    closes = market.closes
    bench = universe.benchmark()
    own = market.bars(ticker)                     # real sessions only: a missing Yahoo bar is a gap, not a flat day
    c = own["close"].dropna()
    if c.empty:
        raise TickerNotFound(ticker)
    ma = technicals.macd(c)
    bb = technicals.bollinger(c)
    df = pd.DataFrame({
        "close": c, "high": own["high"].reindex(c.index), "low": own["low"].reindex(c.index),
        "volume": own["volume"].reindex(c.index), "sma50": c.rolling(50).mean(), "sma200": c.rolling(200).mean(),
        "rsi": technicals.rsi(c), "macd": ma["macd"], "macd_signal": ma["signal"], "macd_hist": ma["hist"],
        "bb_upper": bb["upper"], "bb_lower": bb["lower"],
        "rel_acwi": c / closes[bench].reindex(c.index).ffill(),
    }).iloc[-days:]
    df["rel_acwi"] = 100 * df["rel_acwi"] / df["rel_acwi"].dropna().iloc[0]   # rebased to 100 at the window start
    df.index = df.index.strftime("%Y-%m-%d")
    return clean({"symbol": ticker, "dates": list(df.index), **{k: df[k].tolist() for k in df.columns}})
