"""Index constituents from the fund providers' holdings files: the S&P 500 from SSGA's SPY holdings (the US
stock list) and MSCI ACWI from iShares' ACWI UCITS holdings (sector, region and currency weights for proposals).
Each file is checked (a layout change raises and keeps the cached copy) and cached."""
from __future__ import annotations

import io
import time

import pandas as pd

from . import net, sourcelog
from .config import typed, write_csv
from .paths import CACHE

# State Street publishes SPY's full holdings daily – an official S&P 500 constituent list.
SPY_HOLDINGS = ("https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/"
                "etfs/us/holdings-daily-us-en-spy.xlsx")


SPY_MIN_HOLDINGS = 450  # fewer means the file layout changed; the cached list is kept instead


def spy_holdings() -> pd.DataFrame:
    resp = net.get(SPY_HOLDINGS, timeout=60)
    resp.raise_for_status()
    return parse_spy_holdings(resp.content)


def parse_spy_holdings(content: bytes, min_holdings: int = SPY_MIN_HOLDINGS) -> pd.DataFrame:
    """SSGA's daily SPY holdings xlsx → ticker, name (US stocks only; cash and futures rows dropped)."""
    df = pd.read_excel(io.BytesIO(content), skiprows=4)
    missing = {"Ticker", "Name", "Weight", "Local Currency"} - set(df.columns)
    if missing:
        raise ValueError(f"SPY holdings file has no {', '.join(sorted(missing))} column: has the layout changed?")
    df = df[pd.to_numeric(df["Weight"], errors="coerce").notna() & (df["Local Currency"] == "USD")]
    df = df.dropna(subset=["Ticker"])
    df["ticker"] = df["Ticker"].astype(str).str.strip().str.replace(".", "-", regex=False)
    df = df[df["ticker"].str.replace("-", "").str.isalpha()]
    df = df[["ticker", "Name"]].rename(columns={"Name": "name"}).drop_duplicates("ticker").sort_values("ticker")
    if len(df) < min_holdings:
        raise ValueError(f"only {len(df)} stocks in the SPY holdings file (expected ≥ {min_holdings})")
    return df


def us_constituents(refresh: bool = False, offline: bool = False) -> list[str]:
    """S&P 500 constituents (from SPY holdings), cached for `constituents_max_age_days`.

    A failed download falls back to the cached list (logged in sources.json); `offline` never fetches.
    """

    cache_file = CACHE / "constituents_us.csv"
    cached = pd.read_csv(cache_file)["ticker"].tolist() if cache_file.exists() else []
    max_age = typed().constituents_max_age_days * 86400
    if offline or (not refresh and cached and time.time() - cache_file.stat().st_mtime < max_age):
        return cached
    try:
        from . import ops

        with ops.context(source="constituents"):
            df = spy_holdings()
    except Exception as e:
        if not cached:
            raise
        sourcelog.record("constituents", False, error=f"{type(e).__name__}: {e}; using the cached list", exc=e)
        return cached
    CACHE.mkdir(parents=True, exist_ok=True)
    write_csv(df, cache_file, index=False)
    sourcelog.record("constituents", True, f"{len(df)} stocks")
    return df["ticker"].tolist()


# The UCITS share class tracks the same index as the US-listed ACWI; its holdings file (German locale, as the
# discovery scan's EXSA and CSPX files) gives every stock's GICS sector, country and trading currency.
ACWI_HOLDINGS = ("https://www.ishares.com/de/privatanleger/de/produkte/251850/"
                 "ishares-msci-acwi-ucits-etf/latest-holdings.csv")


ACWI_MIN_HOLDINGS = 1000            # fewer means the file layout changed; the cached file is kept instead


ACWI_FILE = CACHE / "acwi_holdings.csv"


ACWI_COLS = ["ticker", "name", "sector", "country", "region", "currency", "weight"]


# iShares' German country names -> the radar's regions (stock groups); everything else is "other"
_NORDIC = {"Dänemark", "Schweden", "Norwegen", "Finnland", "Island"}


_EUROPE = {"Vereinigtes Königreich", "Deutschland", "Irland", "Schweiz", "Frankreich", "Niederlande", "Spanien",
           "Italien", "Belgien", "Österreich", "Portugal", "Griechenland", "Polen", "Ungarn", "Tschechien",
           "Luxemburg"}


_ASIA = {"Japan", "Taiwan", "Korea", "China", "Hongkong", "Singapur", "Indien", "Malaysia", "Thailand",
         "Indonesien", "Philippinen"}


def acwi_region(country: str) -> str:
    c = (country or "").strip()
    return ("us" if c == "Vereinigte Staaten" else "nordic" if c in _NORDIC else "europe" if c in _EUROPE
            else "asia" if c in _ASIA else "other")


def parse_acwi_holdings(text: str, min_rows: int | None = None) -> pd.DataFrame:
    """The iShares MSCI ACWI UCITS holdings CSV → one row per stock: ticker (iShares'), name, Yahoo-style sector,
    country, region, trading currency and weight (a fraction; the stock rows re-scaled to sum to 1, since cash and
    futures lines are left out)."""
    import csv

    from .discovery.sources import ISHARES_SECTORS

    rows = list(csv.reader(io.StringIO(text)))
    head = next((i for i, r in enumerate(rows) if r and r[0].strip() == "Emittententicker"), None)
    if head is None:
        raise ValueError("no 'Emittententicker' header in the ACWI holdings file: has the layout changed?")
    hdr = [h.strip() for h in rows[head]]
    need = {"Emittententicker", "Name", "Sektor", "Anlageklasse", "Gewichtung (%)", "Standort", "Marktwährung"}
    if need - set(hdr):
        raise ValueError(f"ACWI holdings file has no {', '.join(sorted(need - set(hdr)))} column")
    out = []
    for r in rows[head + 1:]:
        if len(r) != len(hdr):
            continue
        d = dict(zip(hdr, r))
        if d["Anlageklasse"].strip() != "Aktien":
            continue
        try:
            w = float(d["Gewichtung (%)"].strip().replace(".", "").replace(",", "."))
        except ValueError:
            continue
        country = d["Standort"].strip()
        out.append({"ticker": d["Emittententicker"].strip(), "name": d["Name"].strip().title(),
                    "sector": ISHARES_SECTORS.get(d["Sektor"].strip(), d["Sektor"].strip() or "Other"),
                    "country": country, "region": acwi_region(country),
                    "currency": d["Marktwährung"].strip(), "weight": w})
    least = ACWI_MIN_HOLDINGS if min_rows is None else min_rows
    if len(out) < least:
        raise ValueError(f"only {len(out)} stocks in the ACWI holdings file (expected ≥ {least})")
    df = pd.DataFrame(out, columns=ACWI_COLS)
    if not df["weight"].sum() > 0:
        raise ValueError("the ACWI holdings file has no weights")
    df["weight"] = df["weight"] / df["weight"].sum()
    return df


def acwi_holdings(refresh: bool = False, offline: bool = False) -> pd.DataFrame | None:
    """ACWI's stocks with sector, country, region, currency and weight, cached for `constituents_max_age_days`.
    A failed download keeps the cached file (logged in sources.json); None when there is none: callers then say
    that the ACWI weights are unknown, never assume them."""

    cached = pd.read_csv(ACWI_FILE, keep_default_na=False) if ACWI_FILE.exists() else None
    max_age = typed().constituents_max_age_days * 86400
    if offline or (not refresh and cached is not None and time.time() - ACWI_FILE.stat().st_mtime < max_age):
        return cached
    try:
        from . import ops

        with ops.context(source="acwi_holdings"):
            resp = net.get(ACWI_HOLDINGS, timeout=60)
            resp.raise_for_status()
            df = parse_acwi_holdings(resp.content.decode("utf-8-sig", errors="replace"))
    except Exception as e:  # noqa: BLE001 - any failure keeps the cache, logged
        sourcelog.record("acwi_holdings", False, error=f"{type(e).__name__}: {e}"
                        + ("; using the cached file" if cached is not None else ""), exc=e)
        return cached
    CACHE.mkdir(parents=True, exist_ok=True)
    write_csv(df, ACWI_FILE, index=False)
    sourcelog.record("acwi_holdings", True, f"{len(df)} stocks")
    return df


def acwi_weights(holdings: pd.DataFrame | None = None, offline: bool = False) -> dict | None:
    """ACWI's weights by sector, region and currency (fractions summing to 1), or None when unknown."""
    df = acwi_holdings(offline=offline) if holdings is None else holdings
    if df is None or df.empty:
        return None
    return {k: {str(g): float(w) for g, w in df.groupby(k)["weight"].sum().items()}
            for k in ("sector", "region", "currency")}
