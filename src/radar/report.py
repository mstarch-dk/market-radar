"""`radar report`: computes the dashboard and writes reports/dashboard.json (served by the web app) and
reports/summary.json (read by the market brief and research skills), then saves the rank snapshots."""
from __future__ import annotations

import json
from datetime import date

from . import dashboard, ops, snapshot
from .config import write_text
from .fundamentals import context as fcontext
from .jsonsafe import dumps
from .paths import REPORTS

SUMMARY_ROTATION = ("ticker", "name", "quadrant", "rel_r1m", "rel_r3m", "rel_r6m", "rank", "rank_change",
                    "quadrant_local", "ucits", "ucits_name", "isin", "positive_list", "pe", "pe_vs_acwi", "pe_pct")
SUMMARY_MOMENTUM = ("ticker", "name", "sector", "industry", "score", "r3m", "r6m", "from_high", "new", "pe_fy1",
                    "pe_vs_sector", "eps_rev_4w", "eps_rev_12w", "quality", "value", "qv")
SUMMARY_ME = ("symbol", "name", "status", "score", "r1m", "r3m", "rel_r3m", "from_high", "since_buy", "bench_since_buy",
              "last_sell_date", "since_sell", "flags", "pe_fy1", "pe_cy", "pe_vs_sector", "eps_rev_4w", "eps_rev_12w",
              "earnings_date", "pe", "pe_vs_acwi", "quality", "value", "qv")
SUMMARY_QUALITY = ("ticker", "name", "sector", "fund_set", "fund_source", "quality", "value", "qv", "q_n", "v_n",
                   "fcf_yield", "roic", "ev_ebit", "shareholder_yield", "div_years", "momentum", "fund_period_end",
                   "new")
SUMMARY_SOURCES = ("key", "name", "provider", "coverage", "asof", "age_days", "status", "error")


def _plain(row: dict) -> dict:
    """A row without its display gauges: summary.json keeps the keys the skills were written against."""
    return {k: v for k, v in row.items() if k not in ("gauge", "gauges", "val_gauges")}


def summary(d: dict, me: list[dict], portfolios: list[dict] | None = None) -> dict:
    """The compact digest the skills read. Its keys are a contract: change them only together with the skills."""
    cov = d["coverage"]
    mom = d["momentum"]["regions"]
    qual = (d.get("quality") or {}).get("regions", [])
    return {
        "asof": d["asof"], "regime": d["regime"]["overall"],
        "indicators": [_plain(i) for i in d["regime"]["indicators"]],
        "rotation": {g["key"]: [{k: r[k] for k in SUMMARY_ROTATION} for r in g["rows"]] for g in d["rotation"]["groups"]},
        "momentum_top10": {r["key"]: [{k: x[k] for k in SUMMARY_MOMENTUM} for x in r["rows"][:10]] for r in mom},
        "momentum_new_entrants": {r["key"]: r["entrants"] for r in mom},
        "momentum_dropped_out": {r["key"]: r["dropped"] for r in mom},
        "me": [{k: x.get(k) for k in SUMMARY_ME} for x in me],
        "portfolios": portfolios or [],     # your real portfolios' returns over time vs ACWI (performance.summary)
        "momentum_clusters": {r["key"]: r["clusters"] for r in mom},
        # kvalitetsscore and værdiscore (financial statements): the top 10 by K+V per region, and the new ones
        "quality_top10": {r["key"]: [{k: x.get(k) for k in SUMMARY_QUALITY} for x in r["rows"]
                                     if x.get("rank_qv") is not None][:10] for r in qual},
        "quality_new_entrants": {r["key"]: r["entrants"] for r in qual},
        "quality_coverage": {r["key"]: r["coverage"] for r in qual},
        "abtest": {"running": False},      # the forward A/B test's digest (abtest.summary), filled by add_abtest
        "positioning_cot": [_plain(r) for r in d["positioning"]["cot"]],
        "leading_indicators": [_plain(r) for r in d["positioning"]["cli"]],
        "earnings_factset": d["positioning"]["factset"],
        # market valuation (CAPE, Damodaran ERP, yield gap), EPS-revision breadth outside the S&P 500 (Yahoo
        # consensus, weekly snapshots) and contrarian sentiment (AAII, CBOE put/call); None = no data yet
        "valuation": {k: _plain(v) if isinstance(v, dict) else v for k, v in d["positioning"]["valuation"].items()
                      if k != "charts"},
        "revisions_regional": {**d["positioning"]["revisions"],
                               "windows": [w | {"rows": [_plain(r) for r in w["rows"]]}
                                           for w in d["positioning"]["revisions"]["windows"]]},
        "sentiment": {k: ({x: y for x, y in v.items() if x not in ("gauge", "history")} if v else None)
                      for k, v in d["positioning"]["sentiment"].items()},
        "stale_tickers": cov["stale_tickers"],
        "behind_tickers": cov.get("behind_tickers", []),
        "coverage": {
            "regime": cov["regime"], "oldest_input": cov["oldest"], "failing_sources": cov["failing"],
            "stale_sources": cov["stale_sources"], "missing_tickers": cov["missing_tickers"],
            "sources": [{k: r[k] for k in SUMMARY_SOURCES} for r in cov["sources"]],
            "blind_spots": cov["blind_spots"],
        },
    }


def _write(path, data: dict) -> None:
    """Write via a temp file, so a running `radar serve` never reads half a file."""
    write_text(path, dumps(data, indent=1))


def _portfolios() -> list[dict]:
    from . import performance, profile, universe

    universe.ensure_migrated()
    return performance.summary(profile.Market.load())


def add_abtest(market=None) -> None:
    """Put the forward A/B test's digest into summary.json: after the report, and again after the test's refresh
    has replayed the month's picks."""
    from . import abtest, profile

    f = REPORTS / "summary.json"
    if not f.exists() or not abtest.portfolios():
        return
    s = json.loads(f.read_text(encoding="utf-8"))
    s["abtest"] = abtest.summary(market or profile.Market.load())
    _write(f, s)


def build() -> dict:
    c = dashboard.compute()
    d = c.data
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / dashboard.FILE_NAME
    _write(out, d)
    _write(REPORTS / "summary.json", summary(d, c.me, _portfolios()))
    # snapshots after comparing with the previous ones
    today = date.today()
    snapshot.save("rotation", c.rotation.rename(columns={"rs_score": "score"}), today)
    snapshot.save("momentum", c.leaders, today)
    if not c.quality.empty:
        snapshot.save("qv", c.quality, today)
    fcontext.save_week(c.fctx, today)
    try:
        add_abtest()
    except Exception as e:  # noqa: BLE001 - the digest is extra; the report itself is written
        ops.event("error", "job", f"abtest summary: {type(e).__name__}: {e}", source="abtest", exc=e)
    return {"dashboard": str(out), "asof": d["asof"], "regime": d["regime"]["overall"]["label"],
            "stale": len(d["coverage"]["stale_tickers"]), "behind": len(d["coverage"].get("behind_tickers", []))}
