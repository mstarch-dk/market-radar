"""What the radar would have known on a past day D: the inputs of the stop / take-profit rule
(signals/levels.py), each cut at D.

- **Own row** (last, 50/200-day averages, trend, 1-month return): `momentum.metrics_panel`, row D, which equals
  `momentum.metrics(closes.loc[:D])`.
- **Momentum score**: percentile of 12-1, 6- and 3-month returns against every stock in the universe on D, as on
  My holdings (model.score.score_vs). The universe is today's list (survivorship: names that left it are missing).
- **Quadrant** (sector/theme funds; a note only, it doesn't move k): the RRG at the last completed week (W-FRI)
  on or before D.
- **Regime**: computed at the last session of each week and held until the next one. Prices up to that day
  (the last 320 sessions, enough for every window); FRED, OECD CLI and CAPE/ERP only from before their
  publication lag; FactSet reports dated by then. Voting groups are today's choice. Without 200 sessions of
  benchmark history it is missing.
- **Analyst consensus**: the rows fetched on or before D (levels.analyst_view, with its max age).
- **ATR**: Wilder's ATR on adjusted highs/lows/closes, row D.

A missing input moves nothing and is named in the reasons and in `context`, never counted as zero.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .. import external, universe, valuation
from ..config import settings, universe_config
from ..model import inputs as minputs
from ..model import paths as mpaths
from ..model.score import score_vs
from ..signals import levels as lv
from ..signals import momentum, regime, rotation
from ..signals import valuation as sv

REGIME_ROWS = 320          # sessions of prices the regime reads (252-day highs/lows + 10-day smoothing + 1 month)


@dataclass
class Context:
    market: object
    cfg: dict
    stops: dict
    held: dict[str, pd.DataFrame]          # metrics_panel for the replayed symbols
    dist: dict[str, pd.DataFrame]          # r12_1 / r6m / r3m panels for the stock universe
    atr: dict[str, pd.Series]
    quadrants: pd.DataFrame                # W-FRI x fund: quadrant name
    twins: dict[str, str]                  # UCITS twin -> the fund whose quadrant it takes
    analyst: dict[str, pd.DataFrame]       # ticker -> its consensus rows, oldest first
    eligible: set[str]
    sessions: pd.DatetimeIndex             # benchmark calendar
    _regime: dict = field(default_factory=dict, repr=False)
    _week_end: pd.Series | None = field(default=None, repr=False)
    _macro: dict | None = field(default=None, repr=False)
    _atr_by: dict = field(default_factory=dict, repr=False)   # (ticker, atr_days) -> ATR series for other windows

    @classmethod
    def build(cls, market, held: set[str]) -> Context:
        cfg = settings()
        closes = market.closes
        mh = cfg["momentum"]["min_history_days"]
        stocks = sorted({t for g in universe.stock_groups(offline=True).values() for t in g})
        uni = momentum.metrics_panel(closes, stocks, mh)
        panel = momentum.metrics_panel(closes, sorted(held), mh)
        stops = cfg["stops"] | {"analyst_max_age_days": cfg["coverage"]["max_age"]["analyst"]}
        atr = {t: lv.atr(market.highs[t], market.lows[t], closes[t], stops["atr_days"])
               for t in held if t in closes and t in market.highs and t in market.lows}
        bench = universe.benchmark()
        insts = [i for i in universe.etfs() if i.ticker in closes.columns]
        rc = cfg["rotation"]
        quads = pd.DataFrame()
        if insts:
            ratio, mom = rotation.rrg(closes, bench, [i.ticker for i in insts], rc["window"], 10**6)
            quads = pd.DataFrame({t: [rotation.quadrant(r, m) for r, m in zip(ratio[t], mom[t])] for t in ratio.columns},
                                 index=ratio.index)
        twins = {i.ucits: i.ticker for i in insts if i.ucits}
        ah = external.load_analyst()
        analyst = {t: g.sort_values("fetched") for t, g in ah.groupby("ticker")} if not ah.empty else {}
        eligible = minputs.level_universe(minputs.level_etfs(cfg["stops"]), ah)
        sec = universe.sectors(sorted(held))   # stocks you no longer hold have no fresh analyst row: Yahoo's sector says so
        eligible |= set(sec.index[sec["sector"].astype(str).str.strip() != ""])
        return cls(market, cfg, stops, panel, {k: uni[k] for k in ("r12_1", "r6m", "r3m")}, atr, quads, twins,
                   analyst, eligible, closes[bench].dropna().index)

    # ---------------- inputs on day D ----------------

    def row(self, t: str, day: pd.Timestamp) -> dict | None:
        if t not in self.held["last"] or day not in self.held["last"].index:
            return None
        r = {k: self.held[k].at[day, t] for k in ("last", "r1m", "r3m", "r6m", "r12_1", "sma50", "sma200", "above50",
                                                    "above200", "trend_ok", "history")}
        return None if pd.isna(r["last"]) else {k: (None if pd.isna(v) else v) for k, v in r.items()}

    def score(self, t: str, day: pd.Timestamp) -> float | None:
        r = self.row(t, day)
        if r is None or day not in self.dist["r3m"].index:
            return None
        return score_vs(pd.DataFrame({c: self.dist[c].loc[day] for c in self.dist}),
                            pd.Series({c: r[c] if r[c] is not None else float("nan") for c in self.dist}))

    def quadrant(self, t: str, day: pd.Timestamp) -> str | None:
        t = self.twins.get(t, t)
        if self.quadrants.empty or t not in self.quadrants:
            return None
        done = self.quadrants.loc[:day, t]
        done = done[done.index <= day]
        q = done.iloc[-1] if len(done) else None
        return None if q in (None, "n/a") else q

    def week_end(self, day: pd.Timestamp) -> pd.Timestamp | None:
        """The last session of the latest week that has ended by `day` (the day itself when it closes a week)."""
        if self._week_end is None:
            s = self.sessions.to_series()
            self._week_end = s.groupby(self.sessions.to_period("W-FRI")).max().sort_values()
        done = self._week_end[self._week_end <= day]
        return done.iloc[-1] if len(done) else None

    def regime(self, day: pd.Timestamp) -> dict:
        """{label, asof, missing}: the regime as of the last completed week; label None when it can't be read."""
        f = self.week_end(day)
        if f is None:
            return {"label": None, "asof": None, "missing": "no completed week of prices yet"}
        if f not in self._regime:
            self._regime[f] = self._regime_at(f)
        return self._regime[f]

    def _inputs(self) -> dict:
        if self._macro is None:
            ucfg = universe_config()
            cli = external.load_oecd_cli()
            fs = external.load_factset()
            self._macro = {"fred": self.market.fred(), "cli": cli, "cli_labels": ucfg.get("external", {}).get("oecd_cli", {}),
                           "factset": fs, "valuation": valuation.load_market(), "groups": universe.stock_groups(offline=True),
                           "labels": universe.stock_group_labels(), "macro": universe.macro_yahoo(),
                           "votes": minputs.effective_votes()}
        return self._macro

    def _regime_at(self, f: pd.Timestamp) -> dict:
        bench = universe.benchmark()
        if (self.sessions <= f).sum() < 200:
            return {"label": None, "asof": f.date().isoformat(), "missing": "less than 200 sessions of benchmark prices"}
        x, bt = self._inputs(), self.cfg.get("backtest") or {}

        def upto(df, lag):
            return df.loc[:f - pd.Timedelta(days=lag)] if df is not None and not df.empty else df

        closes = self.market.closes.loc[:f].iloc[-REGIME_ROWS:]
        fred = upto(x["fred"], bt.get("fred_lag_days", 1))
        cli_raw = upto(x["cli"], bt.get("oecd_lag_days", 70))
        cli = external.cli_table(cli_raw, x["cli_labels"]) if cli_raw is not None and not cli_raw.empty else pd.DataFrame()
        fs = x["factset"]
        fs = fs[pd.to_datetime(fs["report_date"]) <= f] if not fs.empty and "report_date" in fs else pd.DataFrame()
        fs = fs.sort_values("report_date").iloc[-1].to_dict() if not fs.empty else None
        lag = pd.Timedelta(days=bt.get("valuation_lag_days", 30))
        mk = x["valuation"]
        real10y = fred["DFII10"] if fred is not None and "DFII10" in fred else pd.Series(dtype=float)
        market_val = sv.market(valuation.market_series("cape", mk).loc[:f - lag],
                               valuation.market_series("erp", mk).loc[:f - lag], fs.get("fwd_pe") if fs else None, real10y)
        inds, _ = regime.indicators(closes, fred if fred is not None else pd.DataFrame(), bench, x["groups"], x["labels"],
                                    x["macro"], self.cfg["regime"], cli, fs, market_val)
        regime.apply_freshness(inds, f, self.cfg["coverage"]["max_age"])
        o = regime.overall(inds, dict(x["votes"]))
        return {"label": o["label"] if o["total"] - o["na"] - o["stale"] > 0 else None, "asof": f.date().isoformat(),
                "missing": None if o["total"] - o["na"] - o["stale"] > 0 else "no indicator had data",
                "on": o["on"], "off": o["off"], "na": o["na"], "stale": o["stale"]}

    def analyst_view(self, t: str, day: pd.Timestamp) -> dict | None:
        h = self.analyst.get(t)
        if h is None:
            return None
        h = h[pd.to_datetime(h["fetched"]) <= day]
        if h.empty:
            return None
        return lv.analyst_view(h, t, self.market.closes[t].loc[:day], max_age_days=self.stops["analyst_max_age_days"])

    def atr_at(self, t: str, day: pd.Timestamp, days: int | None = None) -> float | None:
        a = self.atr.get(t)
        if days is not None and days != self.stops["atr_days"]:
            if (t, days) not in self._atr_by:
                m = self.market
                ok = t in m.closes and t in m.highs and t in m.lows
                self._atr_by[(t, days)] = lv.atr(m.highs[t], m.lows[t], m.closes[t], days) if ok else None
            a = self._atr_by[(t, days)]
        if a is None or day not in a.index or pd.isna(a.at[day]):
            return None
        return float(a.at[day])

    # ---------------- the rule on day D ----------------

    def levels(self, t: str, day: pd.Timestamp, anchor: float, stops: dict | None = None) -> dict | None:
        """levels.levels for `t` on `day` with this anchor, from inputs known that day; None without a price or ATR.
        Adds `context` (what each input was: a value, or why it was missing) and a reason per missing input.
        `stops` overrides settings.stops (for testing variants of the rule)."""
        cfg = self.stops | stops if stops else self.stops
        row, atr = self.row(t, day), self.atr_at(t, day, cfg["atr_days"])
        if row is None or atr is None:
            return None
        score = self.score(t, day)
        rg = self.regime(day)
        a = self.analyst_view(t, day)
        quad = self.quadrant(t, day) if t in self.twins or t in self.quadrants else None
        extra = {"score": score, "quadrant": quad}
        if cfg.get("mode") == "trend" and int(cfg.get("trend_sma", 200)) != 200:
            n = int(cfg["trend_sma"])
            if (t, "sma", n) not in self._atr_by:
                self._atr_by[(t, "sma", n)] = mpaths.trend_level(self.market.closes[t], n)
            v = self._atr_by[(t, "sma", n)].get(day)
            extra["trend_level"] = None if v is None or pd.isna(v) else float(v)
        out = lv.levels(row | extra, atr, anchor, rg["label"], a, cfg)
        missing = []
        if score is None:
            missing.append(("Momentum score", "not enough history to rank it against the universe that day"))
        if rg["label"] is None:
            missing.append(("Macro regime", f"not available ({rg['missing']})"))
        if a is None:
            missing.append(("Analyst data", "no consensus fetched by then"))
        elif a.get("stale"):
            missing.append(("Analyst data", f"consensus from {a['fetched']} too old by then"))
        out["reasons"] += [{"signal": s, "effect": 0, "detail": d + ": no adjustment"} for s, d in missing]
        out["context"] = {"score": score, "regime": rg["label"], "regime_week": rg["asof"], "quadrant": quad,
                          "analyst": None if a is None else ("stale" if a.get("stale") else a.get("fetched")),
                          "missing": [s for s, _ in missing]}
        return out
