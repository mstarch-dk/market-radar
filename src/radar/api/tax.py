"""The tax estimate for an income year, and the inputs it needs from you: who owns each account (tax persons),
each holding's ISIN and class, and the losses carried in from before the history. An estimate, not tax advice."""
from __future__ import annotations

import sqlite3
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from .. import errors, userstore
from .. import tax as taxes
from ..api_models import (
    InstrumentIn,
    InstrumentView,
    TaxOpeningIn,
    TaxOpeningView,
    TaxPersonIn,
    TaxPersonView,
    TaxYearView,
)
from ..portfolios import trades
from . import state
from .common import sentence

router = APIRouter()


@router.get("/api/tax", response_model=TaxYearView)
def get_tax(year: int | None = Query(None, ge=1990, le=2100, description="Income year (default: this year)"),
            portfolio: list[int] | None = Query(None, description="Only these accounts (ids)"),
            person: int | None = Query(None, description="Only this tax person's accounts")) -> dict:
    """The estimate for `year`: per account (the ASK's or pension's pool, or the frie midler sales, lager and
    dividends) and per person (share income with the progression limit, capital income), computed now. A year
    without rules is a view with the bases, no tax, and a note."""
    trades.ensure_migrated()
    with state.lock:
        try:
            m = state.market()
        except SystemExit as e:                  # Market.load: no price data yet
            raise HTTPException(503, str(e)) from None
        return taxes.year_report(m, year or date.today().year, portfolio, person)


def _store(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except errors.RadarError:
        raise
    except (ValueError, sqlite3.IntegrityError) as e:
        raise HTTPException(422, sentence(e)) from e


@router.get("/api/tax/persons", response_model=list[TaxPersonView])
def list_tax_persons() -> list[dict]:
    return userstore.tax_persons()


@router.post("/api/tax/persons", response_model=TaxPersonView)
def add_tax_person(body: TaxPersonIn) -> dict:
    pid = _store(userstore.save_tax_person, body.model_dump())
    return next(p for p in userstore.tax_persons() if p["id"] == pid)


@router.put("/api/tax/persons/{pid}", response_model=TaxPersonView)
def edit_tax_person(pid: int, body: TaxPersonIn) -> dict:
    if not any(p["id"] == pid for p in userstore.tax_persons()):
        raise HTTPException(404, f"no tax person {pid}")
    _store(userstore.save_tax_person, body.model_dump(), pid)
    return next(p for p in userstore.tax_persons() if p["id"] == pid)


@router.get("/api/tax/instruments", response_model=list[InstrumentView])
def list_instruments() -> list[dict]:
    return list(userstore.instruments().values())


@router.put("/api/tax/instruments/{symbol}", response_model=InstrumentView)
def set_instrument(symbol: str, body: InstrumentIn) -> dict:
    """Set a holding's ISIN or class by hand (a class of none: decided from the ISIN and the positive list)."""
    _store(userstore.save_instrument, symbol, "manual", **body.model_dump())
    return userstore.instruments()[symbol.strip().upper()]


@router.get("/api/tax/openings", response_model=list[TaxOpeningView])
def list_openings() -> list[dict]:
    return userstore.tax_openings()


@router.post("/api/tax/openings", response_model=TaxOpeningView)
def add_opening(body: TaxOpeningIn) -> dict:
    oid = _store(userstore.add_tax_opening, body.model_dump())
    return next(o for o in userstore.tax_openings() if o["id"] == oid)


@router.delete("/api/tax/openings/{oid}", response_model=int)
def delete_opening(oid: int) -> int:
    if not userstore.delete_tax_opening(oid):
        raise HTTPException(404, f"No opening {oid}.")
    return oid
