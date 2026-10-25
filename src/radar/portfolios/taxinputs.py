"""What the tax estimate needs to know about a holding: its ISIN and its tax class in an income year.

ISINs are filled once per symbol, without overwriting a row set by hand, from (in order) the ISIN a broker import
matched to the symbol, `universe.yaml`'s `isin:` (which belongs to the UCITS listing, `ucits:`, never to the US
ticker it stands next to) and the discovery scan's ISIN map. The class for a year:

    stock            a share (Yahoo's quoteType EQUITY, or a stock the radar tracks)
    pl_fund          a fund whose ISIN is on that year's positive-list sheet
    fund             a foreign fund whose ISIN is not on that year's sheet
    dk_distributing  a Danish distributing fund (only when set by hand)
    unknown          with the reason: a fund without an ISIN, a year without a sheet, a Danish fund off the list
                     (distributing or not: asked, never guessed), an instrument the radar can't tell

A class set by hand wins. Nothing here is a guess: unknown is left out of the estimate by the caller, named."""
from __future__ import annotations

import pandas as pd

from .. import userstore
from ..config import universe_config
from ..discovery import scan
from ..sources import external, positive_list, tracked

UNKNOWN = "unknown"


def universe_isins() -> dict[str, str]:
    """UCITS listing -> ISIN from universe.yaml: the benchmark's and each ETF item's `ucits:` with its `isin:`."""
    out: dict[str, str] = {}
    b = universe_config().get("benchmark") or {}
    if b.get("ucits") and b.get("isin"):
        out[b["ucits"]] = b["isin"]
    for e in tracked.etfs():
        if e.ucits and e.isin:
            out.setdefault(e.ucits, e.isin)
    return out


def discovery_isins() -> dict[str, str]:
    """symbol -> ISIN from the discovery scan's ISIN map (positive-list funds found on Yahoo)."""
    f = scan.ISIN_MAP_FILE
    if not f.exists():
        return {}
    df = pd.read_csv(f, keep_default_na=False, dtype=str)
    if not {"isin", "symbol"} <= set(df.columns):
        return {}
    return {r["symbol"]: r["isin"] for _, r in df.iterrows() if r["symbol"] and r["isin"]}


def fill_instruments(symbols) -> dict[str, dict]:
    """Give each symbol without an ISIN one from the import, universe.yaml or the discovery map (in that order),
    recording where it came from; a manual row is never touched. Returns the instruments after the fill."""
    have = userstore.instruments()
    todo = [s for s in dict.fromkeys(symbols) if s and not (have.get(s) or {}).get("isin")]
    if todo and userstore.exists():
        sources = (("import", userstore.symbol_isins()), ("universe", universe_isins()),
                   ("discovery", discovery_isins()))
        for sym in todo:
            for name, found in sources:
                if sym in found:
                    userstore.save_instrument(sym, name, isin=found[sym])
                    break
        have = userstore.instruments()
    return have


def security_kind(symbol: str) -> str | None:
    """stock, fund, or None when the radar can't tell: from the cached Yahoo detail's quoteType (no request), else
    what universe.yaml tracks."""
    raw, _, _ = external.cached_detail(symbol)
    qt = ((raw or {}).get("info") or {}).get("quoteType")
    if qt == "EQUITY":
        return "stock"
    if qt in ("ETF", "MUTUALFUND"):
        return "fund"
    if symbol in {x for e in tracked.etfs() for x in (e.ticker, e.ucits) if x} | set(universe_isins()):
        return "fund"
    if any(symbol in g for g in tracked.stock_groups(offline=True).values()):
        return "stock"
    return None


def classify(symbol: str, year: int, inst: dict | None, years: dict[int, set[str]] | None,
             kind: str | None) -> tuple[str, str | None]:
    """(class, reason) for an income year; the reason says why a holding is unknown (None otherwise)."""
    inst = inst or {}
    if inst.get("tax_class"):
        return inst["tax_class"], None
    if kind == "stock":
        return "stock", None
    if kind is None:
        return UNKNOWN, "the radar can't tell whether it is a share or a fund: set its class"
    isin = inst.get("isin")
    st = positive_list.status(isin, year, years)
    if st == "no_isin":
        return UNKNOWN, "a fund without an ISIN: enter it, so the positive list can be checked"
    if st == "no_sheet":
        return UNKNOWN, f"no positive-list sheet for {year} in imports/positivliste.xlsx"
    if st == "yes":
        return "pl_fund", None
    if str(isin).upper().startswith("DK"):
        return UNKNOWN, "a Danish fund off the positive list: set whether it is distributing (udloddende)"
    return "fund", None
