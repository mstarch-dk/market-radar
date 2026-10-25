"""Index constituents from the fund providers' holdings files: the S&P 500 from SSGA's SPY holdings (the US
stock list) and MSCI ACWI from iShares' ACWI UCITS holdings (sector, region and currency weights for proposals).
Each file is checked (a layout change raises and keeps the cached copy) and cached."""
from __future__ import annotations

import io
import re
import time
from datetime import date

import pandas as pd

from .. import net, sourcelog
from ..config import typed, write_csv
from ..paths import CACHE, HISTORY

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
        from .. import ops

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


ACWI_COLS = ["ticker", "name", "sector", "country", "region", "currency", "weight", "asof"]


_DE_MONTHS = {"jan": 1, "feb": 2, "mär": 3, "mrz": 3, "apr": 4, "mai": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
              "okt": 10, "nov": 11, "dez": 12}


def acwi_asof(text: str) -> str | None:
    """The holdings file's date ('Fondsposition per,"14.Okt.2026"' on its first lines) as YYYY-MM-DD, or None."""
    for line in text.splitlines()[:5]:
        if line.strip().startswith("Fondsposition per"):
            m = re.search(r"(\d{1,2})\.\s*([A-Za-zäÄ]+)\.?\s*(\d{4})", line)
            month = _DE_MONTHS.get(m.group(2).lower()[:3]) if m else None
            if m and month:
                return date(int(m.group(3)), month, int(m.group(1))).isoformat()
    return None


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
    country, region, trading currency, weight (a fraction; the stock rows re-scaled to sum to 1, since cash, futures
    and fund lines are left out) and the file's date (`asof`, None when the file doesn't say)."""
    import csv

    from ..discovery.sources import ISHARES_SECTORS

    rows = list(csv.reader(io.StringIO(text)))
    head = next((i for i, r in enumerate(rows) if r and r[0].strip() == "Emittententicker"), None)
    if head is None:
        raise ValueError("no 'Emittententicker' header in the ACWI holdings file: has the layout changed?")
    hdr = [h.strip() for h in rows[head]]
    need = {"Emittententicker", "Name", "Sektor", "Anlageklasse", "Gewichtung (%)", "Standort", "Marktwährung"}
    if need - set(hdr):
        raise ValueError(f"ACWI holdings file has no {', '.join(sorted(need - set(hdr)))} column")
    asof = acwi_asof(text)
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
                    "currency": d["Marktwährung"].strip(), "weight": w, "asof": asof})
    least = ACWI_MIN_HOLDINGS if min_rows is None else min_rows
    if len(out) < least:
        raise ValueError(f"only {len(out)} stocks in the ACWI holdings file (expected ≥ {least})")
    df = pd.DataFrame(out, columns=ACWI_COLS)
    if not df["weight"].sum() > 0:
        raise ValueError("the ACWI holdings file has no weights")
    df["weight"] = df["weight"] / df["weight"].sum()
    return df


def acwi_holdings(refresh: bool = False, offline: bool = False, max_age_days: int | None = None) -> pd.DataFrame | None:
    """ACWI's stocks with sector, country, region, currency and weight, cached for `max_age_days` (default
    `constituents_max_age_days`). A failed download keeps the cached file (logged in sources.json); None when there
    is none: callers then say that the ACWI weights are unknown, never assume them."""

    cached = pd.read_csv(ACWI_FILE, keep_default_na=False) if ACWI_FILE.exists() else None
    max_age = (typed().constituents_max_age_days if max_age_days is None else max_age_days) * 86400
    if offline or (not refresh and cached is not None and time.time() - ACWI_FILE.stat().st_mtime < max_age):
        return cached
    try:
        from .. import ops

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


# ---------------- ACWI's weights over time (attribution's benchmark segments) ----------------

# iShares serves only the latest holdings (no past dates; plans/F4-attribution.md, the spike), so the radar keeps
# its own weekly record of ACWI's weights from now on: aggregates only, never the stock list.
SEGMENTS_FILE = HISTORY / "acwi_segments.csv"


SEGMENT_COLS = ["asof", "recorded", "dim", "key", "weight"]


SEGMENT_DIMS = ("sector", "region", "country", "currency", "sector_currency", "region_currency", "region_country")


# iShares' German country names -> English, as the attribution's region proxies name them
COUNTRY_EN = {
    "Vereinigte Staaten": "United States", "Japan": "Japan", "Taiwan": "Taiwan", "Vereinigtes Königreich": "United Kingdom",
    "Kanada": "Canada", "Deutschland": "Germany", "Korea": "Korea", "Schweiz": "Switzerland", "Irland": "Ireland",
    "Frankreich": "France", "China": "China", "Australien": "Australia", "Niederlande": "Netherlands", "Spanien": "Spain",
    "Schweden": "Sweden", "Italien": "Italy", "Dänemark": "Denmark", "Singapur": "Singapore", "Südafrika": "South Africa",
    "Hongkong": "Hong Kong", "Belgien": "Belgium", "Finnland": "Finland", "Israel": "Israel", "Mexiko": "Mexico",
    "Norwegen": "Norway", "Thailand": "Thailand", "Ver. Arabische Emirate": "United Arab Emirates",
    "Malaysia": "Malaysia", "Polen": "Poland", "Österreich": "Austria", "Indonesien": "Indonesia", "Portugal": "Portugal",
    "Griechenland": "Greece", "Peru": "Peru", "Kuwait": "Kuwait", "Ungarn": "Hungary", "Qatar": "Qatar",
    "Katar": "Qatar", "Neuseeland": "New Zealand", "Chile": "Chile", "Türkei": "Turkey", "Philippinen": "Philippines",
    "Kolumbien": "Colombia", "Indien": "India", "Tschechien": "Czech Republic", "Ägypten": "Egypt",
    "Russland": "Russia", "Brasilien": "Brazil", "Saudi-Arabien": "Saudi Arabia", "Island": "Iceland",
    "Luxemburg": "Luxembourg",
}


def country_en(country: str) -> str:
    """The English name, or the German one as written when the map doesn't know it (shown, never dropped)."""
    c = (country or "").strip()
    return COUNTRY_EN.get(c, c)


def acwi_segments(holdings: pd.DataFrame) -> pd.DataFrame:
    """ACWI's weights by sector, region, country and currency, and the cross-tabs sector x currency, region x
    currency and region x country (keys joined by '|'), from the parsed holdings: dim, key, weight."""
    df = holdings.assign(country=holdings["country"].map(country_en))
    df = df.assign(sector_currency=df["sector"] + "|" + df["currency"], region_currency=df["region"] + "|" + df["currency"],
                   region_country=df["region"] + "|" + df["country"])
    total = float(df["weight"].sum())
    out = [pd.DataFrame({"dim": d, "key": g.index.astype(str), "weight": g.to_numpy() / total})
           for d in SEGMENT_DIMS for g in [df.groupby(d)["weight"].sum()]]
    return pd.concat(out, ignore_index=True)


def acwi_segment_history() -> pd.DataFrame:
    """Every weekly snapshot of ACWI's weights recorded so far (SEGMENT_COLS); empty when none is."""
    if not SEGMENTS_FILE.exists():
        return pd.DataFrame(columns=SEGMENT_COLS)
    return pd.read_csv(SEGMENTS_FILE, keep_default_na=False, dtype={"key": str})


def record_acwi_segments(holdings: pd.DataFrame, today: date | None = None) -> str:
    """Append this holdings file's weights to the history, once per ISO week of its date. A file from a week
    already recorded, or older than the newest snapshot, adds nothing; earlier rows are never changed."""
    asof = str(holdings["asof"].iat[0]) if "asof" in holdings and len(holdings) and holdings["asof"].iat[0] else None
    if not asof:
        raise ValueError("the ACWI holdings file has no date ('Fondsposition per'): no snapshot recorded")
    stored = acwi_segment_history()
    day = date.fromisoformat(asof)
    if not stored.empty:
        dates = [date.fromisoformat(d) for d in stored["asof"].unique()]
        if any(d.isocalendar()[:2] == day.isocalendar()[:2] for d in dates):
            return f"week of {asof} already recorded"
        if day < max(dates):
            return f"file of {asof} is older than the last snapshot ({max(dates)}): not recorded"
    new = acwi_segments(holdings).assign(asof=asof, recorded=(today or date.today()).isoformat())[SEGMENT_COLS]
    out = new if stored.empty else pd.concat([stored[SEGMENT_COLS], new], ignore_index=True)
    SEGMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_csv(out, SEGMENTS_FILE, index=False)
    return f"snapshot of {asof} recorded ({stored['asof'].nunique() + 1 if not stored.empty else 1} in all)"


def update_acwi_segments() -> str:
    """`radar run`'s step: fetch ACWI's holdings when older than `attribution.snapshot_days` and record the week's
    weights. A failed download is logged by `acwi_holdings` and the cached file's week is tried instead."""
    df = acwi_holdings(max_age_days=typed().attribution.snapshot_days)
    if df is None or df.empty:
        raise RuntimeError("no ACWI holdings file (downloaded or cached): no snapshot recorded")
    return record_acwi_segments(df)
