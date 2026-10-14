"""Reading trades from broker exports and spreadsheets into transaction rows for the portfolio store.

One pipeline for every source: read the file (CSV with any delimiter and encoding, UTF-16, or Excel) → find the
columns (a preset, or a mapping chosen by hand) → normalize numbers, dates and buy/sell words → match each
instrument to a Yahoo symbol → validate → preview → commit as one import (which can be undone).

Nothing is guessed silently: rows that aren't trades (dividends, transfers) are listed as skipped with the reason,
unclear symbols need confirming, and the preview shows exactly what would be saved.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from functools import cache
from pathlib import Path

import pandas as pd
import yaml

FIELDS = ["date", "type", "symbol", "isin", "name", "quantity", "price", "fee", "currency", "account", "ext_ref"]
REQUIRED = ["date", "quantity", "price"]          # plus one of symbol / isin / name
ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

# generic column names (any language) for files without a preset
GENERIC = {
    "date": ["date", "trade date", "dato", "handelsdato", "handelsdag", "datum"],
    "type": ["type", "transaction type", "side", "buy/sell", "køb/salg", "transaktion", "action"],
    "symbol": ["symbol", "ticker", "yahoo symbol"],
    "isin": ["isin"],
    "name": ["name", "security", "instrument", "navn", "værdipapir"],
    "quantity": ["quantity", "qty", "shares", "antal", "amount", "stk"],
    "price": ["price", "kurs", "pris", "purchase price"],
    "fee": ["fee", "fees", "commission", "kurtage", "gebyr", "courtage"],
    "currency": ["currency", "valuta"],
    "account": ["account", "konto", "depot", "portfolio"],
    "ext_ref": ["id", "trade id", "reference", "nota"],
}
DEFAULT_BUY = ["BUY", "B", "BOUGHT", "KØB", "KØBT", "K"]
DEFAULT_SELL = ["SELL", "S", "SOLD", "SALG", "SOLGT"]


@cache
def presets() -> dict:
    return yaml.safe_load((Path(__file__).with_name("presets.yaml")).read_text(encoding="utf-8"))


# ---------------- reading ----------------

def decode(data: bytes) -> str:
    """Text from bytes: UTF-16 (Nordnet) by its BOM, else UTF-8, else Windows-1252 (Danish exports)."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def read_table(data: bytes, filename: str = "") -> pd.DataFrame:
    """The file as a table of text cells (numbers and dates are parsed later, with the right conventions)."""
    if data[:2] == b"PK" or filename.lower().endswith((".xlsx", ".xlsm")):
        df = pd.read_excel(io.BytesIO(data), dtype=str)
    else:
        text = decode(data)
        sample = "\n".join(text.splitlines()[:20])
        try:
            sep = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
        except csv.Error:
            sep = "\t" if "\t" in sample else ";" if sample.count(";") > sample.count(",") else ","
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False, skipinitialspace=True)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c and not c.startswith("Unnamed")]]
    return df.fillna("").astype(str).apply(lambda s: s.str.strip())


# ---------------- finding the columns ----------------

def _norm(c: str) -> str:
    return re.sub(r"\s+", " ", c.strip().lower())


def map_columns(columns: list[str], aliases: dict[str, list[str]]) -> dict[str, str]:
    """field -> column, matching names case- and space-insensitively."""
    by_norm = {_norm(c): c for c in columns}
    out = {}
    for field, names in aliases.items():
        for n in names:
            if _norm(n) in by_norm and by_norm[_norm(n)] not in out.values():
                out[field] = by_norm[_norm(n)]
                break
    return out


def preset_mapping(columns: list[str], preset: str) -> dict[str, str]:
    """A preset's columns, plus generic names for fields the preset doesn't list (a 'Symbol' column in a
    file that otherwise looks like a Danske export is still used)."""
    m = map_columns(columns, presets()[preset]["columns"])
    for field, col in map_columns([c for c in columns if c not in m.values()], GENERIC).items():
        m.setdefault(field, col)
    return m


def _complete(mapping: dict) -> bool:
    return all(f in mapping for f in REQUIRED) and any(f in mapping for f in ("symbol", "isin", "name"))


def detect(columns: list[str]) -> tuple[str | None, dict[str, str]]:
    """The preset whose columns fit best (all required fields found), and its mapping; else a generic guess."""
    best = (None, {}, 0)
    for key, p in presets().items():
        own = map_columns(columns, p["columns"])          # recognised by its own column names only
        if _complete(own) and len(own) > best[2]:
            best = (key, own, len(own))
    if best[0]:
        return best[0], preset_mapping(columns, best[0])
    return None, map_columns(columns, GENERIC)


# ---------------- normalizing values ----------------

def parse_number(s: str, decimal: str = "auto") -> float | None:
    """'1.234,56', '1,234.56', '1234,5', '-12', '1 234,5 DKK' → float; empty or unreadable → None."""
    s = re.sub(r"[^\d,.\-]", "", str(s).replace("−", "-"))
    if not s or s in ("-", ".", ","):
        return None
    if decimal == "auto":
        if "," in s and "." in s:
            decimal = "," if s.rfind(",") > s.rfind(".") else "."
        elif "," in s:
            decimal = "," if re.search(r",\d{1,2}$", s) or s.count(",") == 1 and not re.search(r",\d{3}$", s) else "."
        else:
            decimal = "."
    if decimal == ",":
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(s: str, formats: list[str] | None = None, dayfirst: bool = True) -> str | None:
    s = str(s).strip()
    if not s:
        return None
    for f in formats or []:
        try:
            return datetime.strptime(s, f).date().isoformat()
        except ValueError:
            continue
    if re.fullmatch(r"\d{8}", s):
        try:
            return datetime.strptime(s, "%Y%m%d").date().isoformat()
        except ValueError:
            return None
    try:
        d = pd.to_datetime(s, dayfirst=dayfirst and not re.match(r"^\d{4}-", s))
    except (ValueError, TypeError):
        return None
    return None if pd.isna(d) else d.date().isoformat()


SAXO_EXCHANGES = {"xcse": ".CO", "xsto": ".ST", "xosl": ".OL", "xhel": ".HE", "xetr": ".DE", "xfra": ".F",
                  "xams": ".AS", "xpar": ".PA", "xbru": ".BR", "xlon": ".L", "xmil": ".MI", "xswx": ".SW",
                  "xvtx": ".SW", "xmad": ".MC", "xlis": ".LS", "xwbo": ".VI", "xdub": ".IR", "xnas": "",
                  "xnys": "", "arcx": "", "bats": "", "xase": "", "xtks": ".T", "xhkg": ".HK"}


def saxo_to_yahoo(sym: str) -> str | None:
    """Saxo's 'NOVOb:xcse' / 'AAPL:xnas' → Yahoo's 'NOVO-B.CO' / 'AAPL'; None if the exchange is unknown."""
    m = re.fullmatch(r"([A-Za-z0-9.\-]+?)([a-z])?:([a-z0-9]+)", sym.strip())
    if not m or m.group(3) not in SAXO_EXCHANGES:
        return None
    base, share_class, ex = m.group(1).upper(), m.group(2), m.group(3)
    return f"{base}{'-' + share_class.upper() if share_class else ''}{SAXO_EXCHANGES[ex]}"


def normalize(df: pd.DataFrame, mapping: dict[str, str], preset: str | None = None,
              default_account: str | None = None) -> tuple[list[dict], list[str]]:
    """Rows as transactions (unresolved: `ident` is what identifies the instrument), plus the watch-only symbols
    (Yahoo exports). Rows that aren't buys or sells are kept with `skip` saying why."""
    p = presets().get(preset or "", {})
    decimal = p.get("decimal", "auto")
    buy = {w.upper() for w in p.get("buy", DEFAULT_BUY)}
    sell = {w.upper() for w in p.get("sell", DEFAULT_SELL)}
    get = lambda r, f: r[mapping[f]] if f in mapping else ""  # noqa: E731
    rows, watch = [], []
    for i, r in df.iterrows():
        sym, isin, name = get(r, "symbol"), get(r, "isin").upper(), get(r, "name")
        if preset == "saxo" and sym:
            sym = saxo_to_yahoo(sym) or sym
        ident = sym or isin or name
        qty = parse_number(get(r, "quantity"), decimal)
        if not ident:
            continue
        if qty is None and p.get("watch_without_quantity"):
            if not sym.startswith(("^", "$$")) and "=" not in sym:
                watch.append(sym)
            continue
        if sym.startswith(("^", "$$")) or "=" in sym:            # Yahoo index, FX and cash rows
            continue
        word = get(r, "type").strip().upper()
        if not word and p.get("default_type"):
            kind = p["default_type"]
        elif word in buy:
            kind = "BUY"
        elif word in sell:
            kind = "SELL"
        elif not word and "type" not in mapping and qty is not None:
            kind = "SELL" if qty < 0 else "BUY"                     # no type column: the sign says it
        else:
            kind = None
        row = {"row": int(i) + 2, "ident": ident, "symbol_in": sym or None, "isin": isin if ISIN_RE.match(isin) else None,
               "name": name or None, "date": parse_date(get(r, "date"), p.get("date_formats"), p.get("dayfirst", True)),
               "type": kind, "quantity": abs(qty) if qty is not None else None,
               "price": abs(v) if (v := parse_number(get(r, "price"), decimal)) is not None else None,
               "fee": abs(parse_number(get(r, "fee"), decimal) or 0.0),
               "currency": get(r, "currency") or None, "account": get(r, "account") or default_account or None,
               "ext_ref": get(r, "ext_ref") or None, "skip": None}
        if kind is None:
            row["skip"] = f"not a buy or sell ({word or 'no type'})"
        elif row["date"] is None:
            row["skip"] = f"unreadable date ({get(r, 'date')!r})"
        elif not row["quantity"] or not row["price"]:
            row["skip"] = "no quantity or price"
        rows.append(row)
    return rows, sorted(set(watch))


# ---------------- matching instruments to Yahoo symbols ----------------

def suggest_symbols(idents: list[tuple[str, str | None, str | None, str | None]], market_has) -> dict[str, dict]:
    """For each (ident, symbol, isin, name): a suggested Yahoo symbol and how it was found, best first:
    remembered → the radar's own ISIN list → the symbol itself when Yahoo has prices → Yahoo search (ISIN, then
    name). `market_has(symbol)` says whether prices exist (it may download them)."""
    from .. import universe, userstore

    isin_cfg = {}
    for e in universe.etfs():
        if e.isin:
            isin_cfg[e.isin.upper()] = e.ucits or e.ticker
    out = {}
    for ident, sym, isin, name in idents:
        cands: list[dict] = []
        for key in filter(None, [isin, sym, name, ident]):
            if (m := userstore.mapped_symbol(key)):
                cands.append({"symbol": m, "how": "remembered"})
                break
        if isin and isin in isin_cfg:
            cands.append({"symbol": isin_cfg[isin], "how": "radar ISIN list"})
        if sym and market_has(sym):
            cands.append({"symbol": sym, "how": "as in the file"})
        for q in filter(None, [isin, name]):
            cands += [{"symbol": h["symbol"], "how": f"Yahoo search for {q}", "name": h.get("name"),
                       "exchange": h.get("exchange")} for h in yahoo_search(q)[:4]]
        seen, uniq = set(), []
        for c in cands:
            if c["symbol"] not in seen:
                seen.add(c["symbol"])
                uniq.append(c)
        out[ident] = {"ident": ident, "isin": isin, "name": name, "candidates": uniq,
                      "chosen": uniq[0]["symbol"] if uniq else None,
                      "certain": bool(uniq) and uniq[0]["how"] in ("remembered", "radar ISIN list", "as in the file")}
    return out


def yahoo_search(q: str) -> list[dict]:
    try:
        import yfinance as yf

        quotes = yf.Search(q, max_results=6, news_count=0).quotes
    except Exception:
        return []
    return [{"symbol": x["symbol"], "name": x.get("longname") or x.get("shortname"),
             "exchange": x.get("exchDisp") or x.get("exchange")}
            for x in quotes if x.get("symbol") and x.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND")]


# ---------------- preview and commit ----------------

def preview(data: bytes, filename: str, get_market, market_has, preset: str | None = None,
            mapping: dict[str, str] | None = None, account: str | None = None,
            symbols: dict[str, str] | None = None) -> dict:
    """What an import would do, without saving anything: the detected format and column mapping, every row
    with its Yahoo symbol (suggested or chosen in `symbols`), skipped rows with the reason, duplicates of stored
    trades, and validation issues. Rows are checked in order, together with the stored trades, so a sale later
    in the file is fine after its buy. `market_has(symbol)` makes sure prices exist (downloading them if needed);
    `get_market()` returns the current price store."""
    from .. import portfolio, userstore

    df = read_table(data, filename)
    detected, guessed = detect(list(df.columns))
    preset = preset if preset in presets() else detected
    if mapping is None:
        mapping = preset_mapping(list(df.columns), preset) if preset else guessed
    rows, watch = normalize(df, mapping, preset, account)
    idents = {r["ident"]: (r["ident"], r["symbol_in"], r["isin"], r["name"]) for r in rows if not r["skip"]}
    matches = suggest_symbols(list(idents.values()), market_has)
    for ident, sym in (symbols or {}).items():
        if ident in matches and sym:
            matches[ident]["chosen"] = sym.strip().upper()
            matches[ident]["certain"] = True

    p = presets().get(preset or "", {})
    stored = userstore.transactions()
    if p.get("snapshot"):                                  # a snapshot replaces its own earlier rows
        stored = [t for t in stored if t["source"] != preset]
    keys = {userstore._key(t) for t in stored}
    refs = {t["ext_ref"] for t in stored if t.get("ext_ref")}
    accounts = {a["name"] for a in userstore.accounts()}
    so_far: list[dict] = []
    for r in rows:
        r["symbol"] = matches.get(r["ident"], {}).get("chosen")
        r["issues"], r["duplicate"] = [], False
        if r["skip"]:
            continue
        if not r["symbol"]:
            r["issues"] = [{"level": "error", "field": "symbol", "message": f"No Yahoo symbol for {r['ident']}: choose one."}]
            continue
        tx = {k: r[k] for k in ("symbol", "date", "type", "quantity", "price", "fee", "account")}
        if tx["account"] and tx["account"] not in accounts:
            tx = tx | {"account": None}                    # a new account from the file: created on commit
        r["duplicate"] = (r["ext_ref"] in refs) if r["ext_ref"] else userstore._key(tx) in keys
        if r["duplicate"]:
            continue
        market_has(tx["symbol"])
        r["issues"] = [i for i in portfolio.validate(tx, get_market(), others=stored + so_far) if i["field"] != "account"]
        so_far.append(tx | {"id": -len(so_far) - 1})
    counts = {"rows": len(rows), "new": sum(1 for r in rows if not r["skip"] and not r["duplicate"]),
              "duplicates": sum(r["duplicate"] for r in rows), "skipped": sum(bool(r["skip"]) for r in rows),
              "errors": sum(any(i["level"] == "error" for i in r["issues"]) for r in rows),
              "warnings": sum(any(i["level"] == "warning" for i in r["issues"]) for r in rows)}
    return {"preset": preset, "preset_label": p.get("label"), "verified": p.get("verified", True) if preset else None,
            "snapshot": bool(p.get("snapshot")), "columns": list(df.columns), "mapping": mapping, "rows": rows,
            "symbols": list(matches.values()), "watch": watch, "counts": counts}


def commit(pv: dict, filename: str, confirm_warnings: bool) -> dict:
    """Save a preview as one import. Refuses if any row has an error, or warnings that weren't confirmed.
    Confirmed symbol matches are remembered for next time."""
    from .. import userstore

    bad = [r for r in pv["rows"] if any(i["level"] == "error" for i in r["issues"])]
    warn = [r for r in pv["rows"] if any(i["level"] == "warning" for i in r["issues"])]
    if bad or (warn and not confirm_warnings):
        raise ValueError(f"{len(bad)} row(s) with errors" if bad else f"{len(warn)} row(s) with warnings to confirm")
    rows = [{k: r[k] for k in ("symbol", "date", "type", "quantity", "price", "fee", "account", "ext_ref")}
            | {"note": None} for r in pv["rows"] if not r["skip"] and not r["duplicate"]]
    source = pv["preset"] or "csv"
    res = userstore.add_import(rows, source, filename, replace_source=pv["snapshot"])
    if pv["snapshot"]:
        userstore.meta_set(f"{source}_watch", pv["watch"])
    for m in pv["symbols"]:
        if m["chosen"]:
            for key in filter(None, [m["isin"], m["ident"]]):
                if key.upper() != m["chosen"]:
                    userstore.map_symbol(key, m["chosen"])
    return res | {"source": source}
