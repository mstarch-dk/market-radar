"""Everything the radar knows about one ticker: price development, momentum, technicals, stop levels,
analyst estimates, valuation, ETF look-through and peers. Used by `radar info` and the web app.

Every section carries `status` (ok | stale | missing), `asof` and `source`, so a reader can tell a real
zero from absent data. Numbers come from the same functions the dashboard uses; nothing is invented when
a source has no answer.
"""
from __future__ import annotations

import pandas as pd

from . import dashboard, external, ingest, mine, money, positive_list, tracked, trades, universe
from .config import settings, universe_config
from .jsonsafe import clean
from .market import Market
from .model import inputs
from .model.score import score_vs
from .signals import gauges as gz
from .signals import levels, momentum, risk, rotation, technicals
from .universe import REGION_SUFFIXES, region_for  # noqa: F401 (re-exported)

OK, STALE, MISSING = "ok", "stale", "missing"
WINDOWS = {"r1w": 5, "r1m": 21, "r3m": 63, "r6m": 126, "r1y": 252}
# the chart's ranges, counted like the return windows (None = year to date)
CHART_RANGES = {"1W": 5, "1M": 21, "3M": 63, "6M": 126, "YTD": None, "1Y": 252, "3Y": 756, "5Y": 1260}


class TickerNotFound(LookupError):
    pass


# ---------------- market data (the Market reader is in market.py) ----------------

def ensure_prices(ticker: str, market: Market | None = None, refresh: bool = False) -> Market:
    """Make sure `ticker` has a current history. Untracked tickers are downloaded (and kept in the price
    store, so the next lookup is fast) but are not added to the daily update. A tracked ticker waits for the
    update, unless `refresh` (the profile's refresh button) asks for its missing sessions now."""
    market = market or Market.load()
    bench = tracked.benchmark()
    is_tracked = ticker in set(universe.all_price_tickers(offline=True))
    have = ticker in market.closes.columns
    behind = have and market.closes[ticker].dropna().index[-1] < market.closes[bench].dropna().index[-1]
    if not have or (behind and (refresh or not is_tracked)):
        ingest.update_prices([ticker])
        market = Market.load()
    if ticker not in market.closes.columns or market.closes[ticker].dropna().empty:
        raise TickerNotFound(f"No Yahoo price data for {ticker}")
    return market


# ---------------- helpers ----------------

def _ret(s: pd.Series, n: int) -> float | None:
    s = s.dropna()
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1) if len(s) > n else None


def _ret_since(s: pd.Series, start: pd.Timestamp) -> float | None:
    s = s.dropna()
    base = s[:start]
    return float(s.iloc[-1] / base.iloc[-1] - 1) if not base.empty else None


def _range_start(s: pd.Series, n: int | None):
    """The base date of a window on `s` (n rows back, or the last close of the previous year), None if too short."""
    if n is None:
        base = s[:pd.Timestamp(year=s.index[-1].year, month=1, day=1) - pd.Timedelta(days=1)]
        return base.index[-1] if not base.empty else None
    return s.index[-1 - n] if len(s) > n else None


def chart_ranges(close: pd.Series, bench: pd.Series, own_close: pd.Series) -> dict[str, dict]:
    """Return, ACWI's return and the difference for each chart range, on the same calendar as the Returns card
    (forward-filled closes), so 1M/YTD/1Y agree with it. A range longer than the stored history runs from the
    first close and says so (`short`). High/low are the ticker's own closes in the range."""
    end = own_close.index[-1]
    s, b = close.dropna()[:end], bench.dropna()[:end]
    out = {}
    for key, n in CHART_RANGES.items():
        start = _range_start(s, n)
        short = start is None
        start = s.index[0] if short else start
        ret = float(s.iloc[-1] / s[start] - 1)
        bb = b[:start]
        acwi = float(b.iloc[-1] / bb.iloc[-1] - 1) if not bb.empty and not b.empty else None
        own = own_close[start:]
        out[key] = {"start": start.strftime("%Y-%m-%d"), "short": short, "ret": ret, "acwi": acwi,
                    "vs_acwi": ret - acwi if acwi is not None else None,
                    "high": float(own.max()) if not own.empty else None, "low": float(own.min()) if not own.empty else None}
    return out


def _windows(s: pd.Series, end) -> dict[str, float | None]:
    """Returns over each window, ending on `end` (the ticker's last bar), plus year to date."""
    s = s.dropna()[:end]
    out = {k: _ret(s, n) for k, n in WINDOWS.items()}
    out["ytd"] = _ret_since(s, pd.Timestamp(year=pd.Timestamp(end).year, month=1, day=1) - pd.Timedelta(days=1))
    return out


def _diff(a: dict, b: dict) -> dict:
    return {k: (a[k] - b[k]) if a.get(k) is not None and b.get(k) is not None else None for k in a}


def sector_etf(region: str, sector: str | None, industry: str | None) -> str | None:
    cfg = universe_config().get("sector_etfs") or {}
    m = cfg.get("europe" if region in ("europe", "nordic") else region) or {}
    for prefix, etf in (m.get("industries") or {}).items():
        if industry and industry.startswith(prefix):
            return etf
    return m.get(sector) if sector else None


def _valuation_snapshot(ticker: str) -> dict | None:
    """The weekly valuation snapshot for this ticker (valuation.py): P/E against its sector peers and EPS
    revisions for a stock, P/E against ACWI for a fund, plus its P/E over the stored weeks. None when the
    snapshot doesn't have it."""
    from . import valuation

    ctx = valuation.context()
    fund = ticker in ctx.etf
    if not fund and ticker not in ctx.now.index:
        return None
    f = ctx.fund(ticker) if fund else ctx.stock(ticker)
    hist = valuation.load_etfs() if fund else valuation.load_stocks()
    col = "pe" if fund else "pe_fy1"
    h = hist[hist["ticker"] == ticker].sort_values("date")
    return {"kind": "fund" if fund else "stock", "asof": ctx.etf_asof if fund else ctx.asof, "weeks": len(h),
            "pe": f.get(col), "pe_vs_sector": f.get("pe_vs_sector"), "pe_vs_acwi": f.get("pe_vs_acwi"),
            "pe_pct": f.get("pe_pct"), "eps_rev_4w": f.get("eps_rev_4w"), "eps_rev_12w": f.get("eps_rev_12w"),
            "sector": None if fund else ctx.sector.get(ticker), "gauges": f["val_gauges"],
            "history": [{"date": pd.Timestamp(d).date().isoformat(), "pe": float(v)}
                        for d, v in zip(h["date"], h[col]) if pd.notna(v)]}


def _section(status: str, source: str, asof=None, **data) -> dict:
    return {"status": status, "source": source, "asof": asof, **data}


def quality_card(ticker: str, market: Market) -> dict | None:
    """The stock's kvalitetsscore and værdiscore card, from the scores of every tracked stock (built once per
    price store and statement update)."""
    from .fundamentals import context as fcontext

    return fcontext.context(market.closes, market.raw_closes(), market.mtime).card(ticker)


# ---------------- the profile ----------------

def build(ticker: str, market: Market | None = None, refresh: bool = False, anonymous: bool = False) -> dict:
    """The full profile of `ticker` (a Yahoo symbol). Raises TickerNotFound without price data. `anonymous`
    builds it as if you held nothing: no status or position, stops anchored on the recent high instead of
    your entry, and no overlap with your holdings, so nothing personal can be read from it."""
    cfg = settings()
    market = ensure_prices(ticker, market)
    closes = market.closes
    bench = tracked.benchmark()
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
    for block, when in ((raw or {}).get("kept") or {}).items():
        notes.append(f"Yahoo {block.replace('_', ' ')}: couldn't refresh, showing data from {when[:10]}")
    detail_asof = raw["fetched"][:10] if raw else None

    is_fund = info.get("quoteType") in ("ETF", "MUTUALFUND")
    look = external.parse_fund((raw or {}).get("fund") or {}, info) if is_fund else None

    # --- identity
    h = trades.holdings() if not anonymous else pd.DataFrame(columns=trades.HOLDING_COLS)
    mine = h[h["symbol"] == ticker]
    status = mine.iloc[0]["status"] if len(mine) else None
    etf_cfg = next((e for e in tracked.etfs() if ticker in (e.ticker, e.ucits)), None)
    region = etf_cfg.region.lower() if etf_cfg else region_for(ticker)
    sec = universe.sectors([ticker]) if info.get("quoteType", "EQUITY") == "EQUITY" else None
    sector = info.get("sector") or (sec.loc[ticker, "sector"] if sec is not None else "") or None
    industry = info.get("industry") or (sec.loc[ticker, "industry"] if sec is not None else "") or None
    if look and look["sector_weights"] and look["sector_weights"][0]["weight"] >= 0.5:
        sector = look["sector_weights"][0]["sector"]       # a sector fund: compare it with that sector
    currency = info.get("currency") or universe.currencies([ticker])[ticker]
    is_tracked = ticker in set(universe.all_price_tickers(offline=True))
    groups = tracked.stock_groups(offline=True)
    isin = etf_cfg.isin if etf_cfg else None
    identity = _section(OK, "Yahoo Finance, config", detail_asof,
        symbol=ticker, name=info.get("longName") or info.get("shortName") or universe.names([ticker])[ticker],
        quote_type=info.get("quoteType") or ("ETF" if etf_cfg else None), currency=currency,
        exchange=info.get("fullExchangeName") or info.get("exchange"), country=info.get("country"),
        sector=sector, industry=industry, website=info.get("website"),
        summary=info.get("longBusinessSummary"), employees=info.get("fullTimeEmployees"),
        region=region, tracked=is_tracked,
        stock_group=next((g for g, ts in groups.items() if ticker in ts), None),
        etf_group=etf_cfg.group if etf_cfg else None, ucits=etf_cfg.ucits if etf_cfg else None,
        isin=isin, positive_list=positive_list.flag(isin, market.positive_list()) if etf_cfg else None,
        my_status=status,
        my_position=clean(mine.iloc[0][["quantity", "avg_price", "first_trade"]].to_dict()) if status == "holding" else None)
    if not is_tracked:
        notes.append("Not tracked by the radar: prices are fetched on lookup, not in the daily update")

    # --- price development
    fx = universe.fx_to_dkk(closes, currency)
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
        score, rank = score_vs(pool, pd.Series(m)), None
        basis = f"percentile against the {pool['region'].iloc[0] if len(pool) else region} stock group (not a member)"
    mom = _section(OK, "radar (prices)", last_date, **{k: v for k, v in m.items() if k != "ticker"},
                   score=score, rank=rank, group_size=int(len(pool)), score_basis=basis,
                   gauges=gz.gauges({"score": score, "from_high": m.get("from_high"), "vol_surge": m.get("vol_surge")}),
                   region_label=tracked.stock_group_labels().get(pool["region"].iloc[0]) if len(pool) else None)

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
        beta_acwi=beta, corr_acwi=corr,
        gauges=gz.gauges({"rsi14": rsi, "bb_pct_b": bb["pct_b"],
                          "macd_atr": ma["hist"] / atr.iloc[-1] if not atr.empty and atr.iloc[-1] else None,
                          "atr_pct": atr.iloc[-1] / close.iloc[-1] if not atr.empty else None, "beta": beta}))

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
                       **(view or {}), recommendations=recs, eps=eps, calendar=cal,
                       gauges=gz.gauges({"upside": (view or {}).get("upside"),
                                         "target_change": (view or {}).get("target_change")}))

    # --- stop / take-profit levels (the same rule as for holdings)
    row = m | {"score": None if score is None or pd.isna(score) else score}
    regime = inputs.current_regime(dashboard.load())
    lv = levels.for_ticker(ticker, closes, market.highs, market.lows, row,
                           mine.iloc[0]["first_trade"] if status == "holding" else None, regime["label"], hist,
                           cfg["stops"] | {"analyst_max_age_days": cfg["coverage"]["max_age"]["analyst"]})
    if lv:
        lv.pop("analyst", None)
    lvl = _section(OK if lv else MISSING, "radar (prices, analyst targets)", last_date,
                   **(lv or {}), regime=regime["label"],
                   gauges=gz.gauges({"stop_dist": (lv or {}).get("stop_pct"), "tp_dist": (lv or {}).get("tp_pct")}))

    # --- risk: weekly DKK returns vs ACWI, factor tilts, and the position size the rule stop allows
    risk_sec = risk_section(ticker, market, close, fx, setf, (lv or {}).get("stop_pct"), last_date)

    # --- fundamentals
    fund = external.parse_fundamentals(info)          # all keys, None where Yahoo has nothing
    if fund.get("market_cap") and not money.is_pence(currency) and fx is not None:
        fund["market_cap_dkk"] = fund["market_cap"] * float(fx.iloc[-1])
    has_fund = any(v is not None for k, v in fund.items() if k not in ("notes", "currency", "financial_currency"))
    fundamentals = _section(raw_status if has_fund else MISSING,
                            "Yahoo Finance", detail_asof, **fund, beta_radar=beta, snapshot=_valuation_snapshot(ticker))

    # --- kvalitetsscore and værdiscore (stored statements)
    quality = None
    if not is_fund and not etf_cfg:
        card = quality_card(ticker, market)
        quality = (_section(OK, "SEC EDGAR" if card["fund_source"] == "edgar" else "Yahoo statements",
                            card["period_end"], **card) if card else
                   _section(MISSING, "statements", None, notes=[
                       "No financial statements stored for this stock: the radar fetches them for the stocks it "
                       "tracks (its lists, your holdings and watchlist), a few each update."]))

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
        inst = next((e for e in tracked.etfs() if e.ticker == target), None) or tracked.Instrument(
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
    watchouts = gz.watchouts({k: v for sec in (tech, mom, lvl, analyst) for k, v in sec["gauges"].items()},
                             skip=set() if status == "holding" else {"stop_dist", "tp_dist"})
    out = {"symbol": ticker, "generated": pd.Timestamp.now().isoformat(timespec="seconds"),
           "identity": identity, "price": price, "momentum": mom, "technicals": tech, "levels": lvl, "risk": risk_sec,
           "analyst": analyst, "fundamentals": fundamentals, "quality": quality, "etf": etf, "peers": peer_sec,
           "context": {"regime": regime, "notes": notes, "errors": (raw or {}).get("errors") or {},
                       "watchouts": watchouts}}
    if not anonymous:   # your market views are personal, like your positions
        from . import market_views

        out["views"] = market_views.align_profile(identity, closes)
    return _checked(clean(out))


def _checked(p: dict) -> dict:
    """A profile against api_models.Profile (what the ticker page reads; extra fields an error): a shape the app
    can't show fails here, for `radar info` and the API alike, naming the field."""
    from pydantic import ValidationError

    from . import api_models

    try:
        api_models.Profile.model_validate(p)
    except ValidationError as e:
        err = e.errors()[0]
        raise ValueError(f"the profile of {p.get('symbol')} doesn't match api_models.Profile: "
                         f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}") from None
    return p


def risk_section(ticker: str, market: Market, close: pd.Series, fx: pd.Series | None, sector_etf_: str | None,
                 stop_pct, asof) -> dict:
    """Risk statistics in DKK over the configured windows (see signals/risk.py), factor tilts vs ACWI (the factor
    ETFs and the sector ETF) and the risk budget at the rule stop."""
    rc = settings()["risk"]
    closes = market.closes
    bench = tracked.benchmark()
    usd = universe.fx_to_dkk(closes, universe.currencies([bench])[bench])
    if fx is None or usd is None:
        return _section(MISSING, "radar (prices, FRED 3m T-bill)", asof, currency="DKK", benchmark=bench,
                        windows={}, factors=None, budget=None, notes=["no DKK rate for this currency"])

    def dkk(px: pd.Series, rate: pd.Series) -> pd.Series:
        return risk.weekly((px * rate.reindex(px.index).ffill()).dropna())

    y = dkk(close, fx)
    mkt = dkk(closes[bench].dropna(), usd)
    rf = market.fred()["DGS3MO"] if "DGS3MO" in market.fred() else None
    windows = {k: risk.window_stats(y, mkt, rf, n, rc["min_weeks"]) for k, n in rc["windows"].items()}
    windows = {k: v for k, v in windows.items() if v}
    tilts = {f: dkk(closes[f].dropna(), usd) for f in rc["factors"] if f in closes and f != ticker}
    if sector_etf_ and sector_etf_ in closes and sector_etf_ != ticker:
        tilts[f"sector {sector_etf_}"] = dkk(closes[sector_etf_].dropna(), usd)
    longest = max(rc["windows"].values())
    factors = risk.factor_loadings(y, mkt, tilts, rf, longest, rc["min_weeks"]) if tilts else None
    notes = []
    if rf is None:
        notes.append("no risk-free rate yet (FRED DGS3MO): Sharpe and Sortino are not computed, alpha uses raw returns")
    return _section(OK if windows else MISSING, "radar (prices, FRED 3m T-bill)", asof, currency="DKK", benchmark=bench,
                    windows=windows, factors=factors, budget=risk.risk_budget(stop_pct, rc["budget"]),
                    budget_risk=rc["budget"], notes=notes)


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
    bench = tracked.benchmark()
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
    ranges = chart_ranges(closes[ticker], closes[bench], c)
    return clean({"symbol": ticker, "dates": list(df.index), **{k: df[k].tolist() for k in df.columns}, "ranges": ranges})


# ---------------- several tickers side by side ----------------

# (label, path into the profile, direction: "higher" / "lower" is better, None = context only)
COMPARE_METRICS = [
    ("Momentum score (region)", "momentum.score", "higher"),
    ("Return 1m", "price.returns.r1m", "higher"),
    ("Return 3m", "price.returns.r3m", "higher"),
    ("Return 6m", "price.returns.r6m", "higher"),
    ("Return 12-1m", "momentum.r12_1", "higher"),
    ("Return 6m in DKK", "price.returns_dkk.r6m", "higher"),
    ("vs ACWI 3m", "price.vs_acwi.r3m", "higher"),
    ("From 52w high", "momentum.from_high", "higher"),
    ("Trend intact", "momentum.trend_ok", None),
    ("RSI 14", "technicals.rsi14", None),
    ("Volatility 1y (DKK)", "risk.windows.1y.vol_ann", "lower"),
    ("Beta 3y", "risk.windows.3y.beta", None),
    ("Downside beta 3y", "risk.windows.3y.downside_beta", "lower"),
    ("Alpha 3y (annual)", "risk.windows.3y.alpha_ann", "higher"),
    ("Alpha 3y t-stat", "risk.windows.3y.alpha_t", None),
    ("Sharpe 3y", "risk.windows.3y.sharpe", "higher"),
    ("Max drawdown 3y", "risk.windows.3y.max_dd", "higher"),
    ("P/E on this year's EPS estimate", "derived.pe_0y", "lower"),
    ("P/E on next year's EPS estimate", "derived.pe_1y", "lower"),
    ("Forward P/E (Yahoo's basis)", "fundamentals.forward_pe", None),
    ("EV/EBITDA", "fundamentals.ev_ebitda", "lower"),
    ("Revenue growth", "fundamentals.revenue_growth", "higher"),
    ("Earnings growth", "fundamentals.earnings_growth", "higher"),
    ("Operating margin", "fundamentals.operating_margin", "higher"),
    ("Return on equity", "fundamentals.return_on_equity", "higher"),
    ("Debt/equity", "fundamentals.debt_to_equity", "lower"),
    ("Dividend yield", "fundamentals.dividend_yield", None),
    ("Kvalitetsscore", "quality.quality", "higher"),
    ("Værdiscore", "quality.value", "higher"),
    ("FCF yield", "derived.fcf_yield", "higher"),
    ("ROIC", "derived.roic", "higher"),
    ("EV/EBIT", "quality.ev_ebit", "lower"),
    ("Shareholder yield", "derived.shareholder_yield", "higher"),
    ("Analyst upside", "analyst.upside", "higher"),
    ("Analyst target change 30d", "analyst.target_change", "higher"),
    ("EPS estimate change 30d (this year)", "analyst.eps.0y.chg_30d", "higher"),
    ("Next earnings", "analyst.calendar.next_earnings", None),
    ("Distance to rule stop", "levels.stop_pct", None),
    ("Position size at 1% risk", "risk.budget", None),
]


def _get(d, path: str):
    """Value at a dotted path; list items are matched on their `period` (e.g. analyst.eps.0y)."""
    for part in path.split("."):
        if isinstance(d, list):
            d = next((x for x in d if isinstance(x, dict) and x.get("period") == part), None)
        elif isinstance(d, dict):
            d = d.get(part)
        else:
            return None
        if d is None:
            return None
    return d


def _derived(p: dict) -> dict:
    """P/E on the consensus EPS for this and next fiscal year, so the basis is explicit (Yahoo's `forwardPE`
    may use either). Only when the EPS is quoted in the price's currency; otherwise null, not a mixed ratio."""
    out = {}
    price, ccy = p["price"]["last"], p["price"]["currency"]
    for key, period in (("pe_0y", "0y"), ("pe_1y", "+1y")):
        e = next((x for x in p["analyst"]["eps"] if x["period"] == period), None)
        ok = e and e.get("eps") and e["eps"] > 0 and (e.get("currency") or ccy) == ccy
        out[key] = price / e["eps"] if ok else None
    metrics = {m["key"]: m.get("value") for m in ((p.get("quality") or {}).get("metrics") or [])}
    for key in ("fcf_yield", "roic", "shareholder_yield"):
        out[key] = metrics.get(key)
    return out


def compare(symbols: list[str], personal: bool = False, market: Market | None = None,
            portfolios: list[int] | None = None) -> dict:
    """Several tickers side by side, with ACWI as the always-present alternative: full profiles, the market
    regime, weekly-return correlations (DKK) and a table of key metrics with the best value per row. Without
    `personal` the profiles are built anonymously (see build); with it, "your holdings" are these portfolios
    (ids; default: your real ones). An unknown ticker becomes an error entry."""
    market = market or Market.load()
    bench = tracked.benchmark()
    rc = settings()["risk"]
    tickers: dict[str, dict] = {}
    for sym in dict.fromkeys(s.strip().upper() for s in symbols):
        try:
            market = ensure_prices(sym, market)
            tickers[sym] = build(sym, market, anonymous=not personal)
        except TickerNotFound as e:
            tickers[sym] = {"error": str(e)}
    ok = {s: p for s, p in tickers.items() if "error" not in p}

    # ACWI: the zero-effort alternative every candidate has to beat
    closes = market.closes
    usd = universe.fx_to_dkk(closes, universe.currencies([bench])[bench])
    b = closes[bench].dropna()
    mkt = risk.weekly((b * usd.reindex(b.index).ffill()).dropna()) if usd is not None else None
    rf = market.fred()["DGS3MO"] if "DGS3MO" in market.fred() else None
    # ACWI against itself: beta 1 and alpha 0 by definition; the regression's error terms are numerical noise
    self_fit = {"beta_se": None, "r2": None, "alpha_t": None, "idio_vol_ann": None, "downside_beta": 1.0}
    bench_block = {"symbol": bench, "name": universe.names([bench]).get(bench), "returns": _windows(b, b.index[-1]),
                   "risk": {k: (w | self_fit | {"alpha_ann": 0.0, "beta": 1.0, "corr": 1.0}) if w else None
                            for k, n in rc["windows"].items()
                            for w in [risk.window_stats(mkt, mkt, rf, n, rc["min_weeks"]) if mkt is not None else None]}}

    # correlations of weekly DKK returns: the candidates, ACWI, and (personal) the current holdings
    series = {}
    for sym in [*ok, bench] + (sorted(set(trades.holdings(portfolios).query("status == 'holding'")["symbol"]) - set(ok))
                               if personal else []):
        if sym not in closes:
            continue
        fx = universe.fx_to_dkk(closes, universe.currencies([sym])[sym])
        if fx is not None:
            s = closes[sym].dropna()
            series[sym] = risk.weekly((s * fx.reindex(s.index).ffill()).dropna())
    corr = risk.correlation(series, rc["windows"]["1y"], rc["min_weeks"])

    bench_profile = {"price": {"returns": bench_block["returns"]}, "risk": {"windows": bench_block["risk"]}}
    derived = {s: _derived(p) for s, p in ok.items()}
    table = []
    for label, path, direction in COMPARE_METRICS:
        values = {s: clean(_get(p | {"derived": derived[s]}, path)) for s, p in ok.items()}
        acwi = clean(_get(bench_profile, path))
        if acwi is not None:
            values[bench] = acwi
        nums = {s: v for s, v in values.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
        best = (max(nums, key=nums.get) if direction == "higher" else min(nums, key=nums.get)) \
            if direction and len(nums) > 1 else None
        table.append({"metric": label, "path": path, "direction": direction, "values": values, "best": best})

    d = dashboard.load()
    regime = None
    if d:
        overall, inds = inputs.regime_now(d)                            # with your current choice of voting groups
        regime = {"asof": d["asof"], "overall": overall,
                  "indicators": [{k: i.get(k) for k in ("name", "value", "status", "gauge")} for i in inds]}
    out = {"generated": pd.Timestamp.now().isoformat(timespec="seconds"),
           "asof": closes[bench].dropna().index[-1].date().isoformat(),
           "personal_included": personal, "regime": regime, "benchmark": bench_block,
           "tickers": tickers, "correlation": corr, "table": table}
    if personal:
        rot = [r for g in (d or {}).get("rotation", {}).get("groups", []) for r in g["rows"]]
        rows = mine.table(closes, market.highs, market.lows, market.volumes, market.raw_closes(), market.leaders(), rot,
                          (regime or {}).get("overall", {}).get("label"), settings(), sessions=lambda s: market.bars(s)["close"],
                          portfolios=portfolios)
        out["mine"] = {r["symbol"]: r for r in rows if r["symbol"] in ok}
    return clean(out)
