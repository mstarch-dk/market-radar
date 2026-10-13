"""`radar report`: computes the dashboard and writes reports/dashboard.json (served by the web app) and
reports/summary.json (read by the market brief and research skills), then saves the rank snapshots."""
from __future__ import annotations

import json
from datetime import date

from . import dashboard, snapshot
from .config import REPORTS

SUMMARY_ROTATION = ("ticker", "name", "quadrant", "rel_r1m", "rel_r3m", "rel_r6m", "rank", "rank_change",
                    "quadrant_local", "ucits", "ucits_name", "isin", "positive_list")
SUMMARY_MOMENTUM = ("ticker", "name", "sector", "industry", "score", "r3m", "r6m", "from_high", "new")
SUMMARY_ME = ("symbol", "name", "status", "score", "r1m", "r3m", "rel_r3m", "from_high", "since_buy", "bench_since_buy",
              "last_sell_date", "since_sell", "flags")
SUMMARY_SOURCES = ("key", "name", "provider", "coverage", "asof", "age_days", "status", "error")


def summary(d: dict, me: list[dict]) -> dict:
    """The compact digest the skills read. Its keys are a contract: change them only together with the skills."""
    cov = d["coverage"]
    mom = d["momentum"]["regions"]
    return {
        "asof": d["asof"], "regime": d["regime"]["overall"],
        "indicators": [{k: v for k, v in i.items() if k != "gauge"} for i in d["regime"]["indicators"]],
        "rotation": {g["key"]: [{k: r[k] for k in SUMMARY_ROTATION} for r in g["rows"]] for g in d["rotation"]["groups"]},
        "momentum_top10": {r["key"]: [{k: x[k] for k in SUMMARY_MOMENTUM} for x in r["rows"][:10]] for r in mom},
        "momentum_new_entrants": {r["key"]: r["entrants"] for r in mom},
        "momentum_dropped_out": {r["key"]: r["dropped"] for r in mom},
        "me": [{k: x.get(k) for k in SUMMARY_ME} for x in me],
        "momentum_clusters": {r["key"]: r["clusters"] for r in mom},
        "positioning_cot": d["positioning"]["cot"], "leading_indicators": d["positioning"]["cli"],
        "earnings_factset": d["positioning"]["factset"],
        "stale_tickers": cov["stale_tickers"],
        "coverage": {
            "regime": cov["regime"], "oldest_input": cov["oldest"], "failing_sources": cov["failing"],
            "stale_sources": cov["stale_sources"], "missing_tickers": cov["missing_tickers"],
            "sources": [{k: r[k] for k in SUMMARY_SOURCES} for r in cov["sources"]],
            "blind_spots": cov["blind_spots"],
        },
    }


def _write(path, data: dict) -> None:
    """Write via a temp file, so a running `radar serve` never reads half a file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)


def build() -> dict:
    c = dashboard.compute()
    d = c.data
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / dashboard.FILE_NAME
    _write(out, d)
    _write(REPORTS / "summary.json", summary(d, c.me))
    # snapshots after comparing with the previous ones
    today = date.today()
    snapshot.save("rotation", c.rotation.rename(columns={"rs_score": "score"}), today)
    snapshot.save("momentum", c.leaders, today)
    return {"dashboard": str(out), "asof": d["asof"], "regime": d["regime"]["overall"]["label"],
            "stale": len(d["coverage"]["stale_tickers"])}
