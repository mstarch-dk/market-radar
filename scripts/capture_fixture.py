"""Record a trimmed copy of a source's real answer into tests/fixtures/, for contract tests.

    uv run python scripts/capture_fixture.py --list
    uv run python scripts/capture_fixture.py fred_DGS10 [--dry-run]

Run by hand when a source changed (a failing `pytest -m network`) or a parser gets a new contract test; never in
CI. Requests go through net.get / net.yf(), so they are paced and recorded like any other. Copies are trimmed to
a few rows or tickers: enough to pin the format, not a copy of the data (see DATA_LICENSE.md). Replace any prose
(report text, company descriptions) with invented text in the same wording before committing; commit the file
with the printed source line in the message.
"""
from __future__ import annotations

import argparse
import io
import sys
from datetime import date, timedelta
from pathlib import Path

from radar import net
from radar.sources import external, sentiment

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
TODAY = date.today()


def _text(url: str) -> str:
    r = net.get(url, timeout=60)
    r.raise_for_status()
    return r.text


def _csv_tail(text: str, rows: int) -> str:
    lines = text.splitlines()
    return "\n".join(lines[:1] + lines[1:][-rows:]) + "\n"


def fred(sid: str):
    return lambda: (f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}",
                    _csv_tail(_text(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"), 25))


def ecb_monthly():
    url = external.ECB_URL.format(key="FM/M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA",
                                  start=(TODAY - timedelta(days=400)).isoformat())
    return url, _csv_tail(_text(url), 12)


def oecd_cli():
    areas = list(external.cfg().get("oecd_cli", {}))
    url = external.OECD_CLI_URL.format(areas="+".join(areas), start=(TODAY - timedelta(days=120)).strftime("%Y-%m"))
    return url, _text(url)


def yahoo_download():
    """A multi-ticker yf.download frame as the radar asks for it (unadjusted, grouped by ticker, tz-naive dates),
    including a symbol Yahoo doesn't know. Saved as parquet: the MultiIndex columns survive."""
    yf = net.yf()
    tickers = ["SPY", "RHM.DE", "7203.T", "NOT-A-TICKER.XX"]
    raw = yf.download(tickers, start=(TODAY - timedelta(days=10)).isoformat(), auto_adjust=False,
                      group_by="ticker", threads=False, progress=False)
    buf = io.BytesIO()
    raw.to_parquet(buf)
    return f"yfinance.download({tickers})", buf.getvalue()


def cboe():
    for back in range(8):
        d = TODAY - timedelta(days=back)
        r = net.get(sentiment.CBOE_URL.format(d=d), timeout=30, expected=(403, 404))
        if r.status_code == 200:
            return sentiment.CBOE_URL.format(d=d), r.text
    raise SystemExit("no CBOE day in the last week")


def trim_companyfacts(js: dict, years: int = 4) -> dict:
    """Company facts cut to the tags the parser reads and the last `years` years of period ends."""
    from radar.fundamentals import items

    cutoff = (TODAY - timedelta(days=365 * years)).isoformat()
    keep = items.edgar_tags()
    out = {k: v for k, v in js.items() if k != "facts"} | {"facts": {}}
    for tax, tags in js.get("facts", {}).items():
        for tag, node in tags.items():
            name = f"dei:{tag}" if tax == "dei" else tag
            if name not in keep:
                continue
            units = {u: [r for r in rows if r.get("end", "") >= cutoff] for u, rows in node.get("units", {}).items()}
            out["facts"].setdefault(tax, {})[tag] = {"label": node.get("label"), "units": units}
    return out


def edgar_aapl(file: str | None = None):
    """Apple's company facts (a 10-Q year with year-to-date cash flows, a September fiscal year), trimmed. With
    --file, an answer saved earlier is trimmed instead (a fetch needs the SEC contact set in the data folder)."""
    import json

    from radar.fundamentals import edgar

    if file:
        return f"{file} (saved from {edgar.FACTS_URL.format(cik=320193)})", json.dumps(trim_companyfacts(
            json.loads(Path(file).read_text(encoding="utf-8"))))
    return edgar.FACTS_URL.format(cik=320193), json.dumps(trim_companyfacts(edgar.fetch_companyfacts(320193,
                                                                                                    edgar.headers())))


def yahoo_statements(file: str | None = None):
    """Yahoo statements for a US quarterly reporter and a UK half-year reporter, as yfinance frames (split JSON),
    cut to the lines the parser reads."""
    import json

    from radar.fundamentals import items, yahoo

    lines = {n for i in items.ITEMS for n in i.yahoo}
    out = {}
    for t in ("AAPL", "RR.L"):
        raw = yahoo.fetch_statements(t)
        out[t] = {f"{st} {freq}": json.loads(df[df.index.isin(lines)].to_json(orient="split", date_format="iso"))
                  for (st, freq), df in raw["blocks"].items()}
    return "yfinance Ticker.get_income_stmt / get_cash_flow / get_balance_sheet (AAPL, RR.L)", json.dumps(out)


SOURCES = {   # name → (file name, capture)
    "fred_DGS10": ("fred_DGS10.csv", fred("DGS10")),
    "ecb_monthly": ("ecb_euribor_monthly.csv", ecb_monthly),
    "oecd_cli": ("oecd_cli.csv", oecd_cli),
    "yahoo_download": ("yahoo_download_batch.parquet", yahoo_download),
    "cboe": ("cboe_daily_options.json", cboe),
    "edgar_aapl": ("edgar_companyfacts_aapl.json", edgar_aapl),
    "yahoo_statements": ("yahoo_statements.json", yahoo_statements),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("source", nargs="?")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="fetch and report, write nothing")
    ap.add_argument("--file", help="edgar_aapl: trim this saved answer instead of fetching")
    a = ap.parse_args(argv)
    if a.list or not a.source:
        print("\n".join(f"{k:16} → tests/fixtures/{f}" for k, (f, _) in SOURCES.items()))
        return 0
    if a.source not in SOURCES:
        print(f"unknown source {a.source!r}; --list shows them", file=sys.stderr)
        return 2
    name, capture = SOURCES[a.source]
    where, body = capture(a.file) if a.file else capture()
    data = body.encode() if isinstance(body, str) else body
    print(f"{a.source}: {len(data):,} bytes from {where}, captured {TODAY}")
    if not a.dry_run:
        (FIXTURES / name).write_bytes(data)
        print(f"wrote tests/fixtures/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
